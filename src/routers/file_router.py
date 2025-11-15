import os
import uuid
import asyncio
from datetime import datetime, timezone
import logging
from starlette.status   import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi            import APIRouter, HTTPException, UploadFile, Request, Depends, Form
from fastapi.responses  import FileResponse, JSONResponse, StreamingResponse

from src.transport.rabbitmq.producer import RPCProducer
from src.config.app_config import settings
from src.utils.files_utils import get_file_extension_by_content_type
from src.utils.sse_utils import get_sse_headers
from src.utils.upload_utils import FileUploadService
from src.utils.sse_service_registry import sse_registry
from src.utils.sse_formatter import SSEEventFormatter
from src.dependencies import verify_captcha_token

router = APIRouter(prefix='/files', tags=["files"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    request: Request,
    _: None = Depends(verify_captcha_token)
) -> JSONResponse:
    logger.info(f"File upload started. Filename: {file.filename}, Content-Type: {file.content_type}")
    
    file_tmp_name = ''
    
    try:
        # Получаем сессию пользователя
        session = request.state.session.get_session()
        
        if (session.get('pending', False)):
            raise HTTPException(400, {"code": "file_processing", "detail": "Файл уже в процессе обработки. Пожалуйста, дождитесь завершения."})

        if (session.get('need_download', False)):
            raise HTTPException(400, {"code": "file_download_pending", "detail": "Пожалуйста, скачайте предыдущий файл перед загрузкой нового."})

        session['pending'] = True
    
        temp_dir = settings.TEMP_DIR
        
        if (os.path.exists(temp_dir) is False):
            os.makedirs(temp_dir)
            
        if (session.get('last_uploaded_file')):
            # Удаляем предыдущий временный файл, если он существует
            previous_file_path = session['last_uploaded_file'].get("file_path", "")
            if previous_file_path and os.path.exists(previous_file_path):
                try:
                    os.remove(previous_file_path)
                    session['last_uploaded_file'] = None
                    logger.info(f"Previous temporary file removed: {previous_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove previous temporary file `{previous_file_path}`: {str(e)}")

        file_id = uuid.uuid4().hex  # Генерируем уникальный идентификатор файла
        file_ext = get_file_extension_by_content_type(file.content_type if file.content_type else "")

        file_tmp_name = f"{file_id}.{file_ext}" if file_ext else file_id
        file_name_without_ext, _ = os.path.splitext(file_tmp_name)

        temp_file_path = os.path.join(temp_dir, file_tmp_name)  # Временный путь для сохранения файла
        with open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        

        producer: RPCProducer = RPCProducer()
        await producer.connect()
        
        await producer.call(
            method="ml.execute",
            params={
                "data": {
                    "name": file_name_without_ext,
                    "path": temp_file_path
                }
            },
            timeout=240.
        )

        # Сохраняем метаданные файла в сессию пользователя
        session['last_uploaded_file'] = {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": temp_file_path,
            "content_type": file.content_type,
            "extension": file_ext,
            "size": file.size,
            "upload_time": datetime.now(timezone.utc).isoformat()
        }

        session['pending'] = False
        session['need_download'] = True

        return JSONResponse(
            {"code": "success", "detail": "Файл успешно обработан."},
            status_code=200
        )
    
    except HTTPException as http_exc:
        session['pending'] = False
        session['need_download'] = False 
        
        logger.error(f"HTTP file upload error: {str(http_exc.detail)}", exc_info=True)
        
        try:
            session['last_uploaded_file'] = None
            
            if (file_tmp_name and os.path.exists(file_tmp_name)):
                os.remove(file_tmp_name)
            
            logger.info(f"Current temporary file removed: {file_tmp_name}")
        except Exception as e:
            pass
        
        raise HTTPException(http_exc.status_code, http_exc.detail)
        
    except Exception as e:
        session['pending'] = False
        session['need_download'] = False 
        
        try:
            session['last_uploaded_file'] = None
            
            if (file_tmp_name and os.path.exists(file_tmp_name)):
                os.remove(file_tmp_name)
            
            logger.info(f"Current temporary file removed: {file_tmp_name}")
        except Exception as e:
            pass
        
        # Любые другие ошибки
        logger.error(f"Unexpected file upload error: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Internal server error: {str(e)}")

@router.get("/session/status")
async def get_session_status(request: Request) -> JSONResponse:
    """
    Получение статуса сессии пользователя.
    Возвращает информацию о текущем состоянии обработки файла.
    
    :param request: Объект запроса FastAPI
    :return: JSON с данными о статусе сессии
    """
    logger.info("Session status requested.")
    
    try:
        session = request.state.session.get_session()
        
        # Получаем базовые флаги состояния
        pending = session.get('pending', False)
        need_download = session.get('need_download', False)
        
        # Получаем метаданные файла если они есть
        file_metadata = session.get('last_uploaded_file', {})
        
        # Формируем минимальный ответ
        response_data = {
            "pending": pending,
            "need_download": need_download,
            "file": None
        }
        
        # Если есть файл для скачивания, добавляем его метаданные
        if need_download and file_metadata:
            response_data["file"] = {
                "filename": file_metadata.get("filename", ""),
                "size": file_metadata.get("size", 0),
                "upload_time": file_metadata.get("upload_time", "")
            }
        
        logger.info(f"Session status: pending={pending}, need_download={need_download}")
        
        return JSONResponse(response_data, status_code=200)
        
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, {"code": "internal_server_error", "detail": "Ошибка получения статуса сессии"})


@router.get("/download/")
async def download_file(request: Request) -> FileResponse:
    """
    Загрузка файла по данным сессии пользователя.
    
    :param request: Объект запроса FastAPI
    :return: Файл
    :raises HTTPException: Если файл не найден или произошла ошибка
    """
    logger.info(f"File download requested.")
    
    try:
        # Получаем метаданные файла из сессии
        session = request.state.session.get_session()
        file_metadata = session.get('last_uploaded_file', {})
        
        file_path = file_metadata.get("file_path", "")
        logger.info(f"Looking for file with path: `{file_path}`")

        # Ищем файл
        if not os.path.exists(file_path):
            logger.error(f"No files found for File ID: {file_metadata.get('file_id', '')}")
            raise HTTPException(404, {"code": "file_not_found", "detail": "Файл не найден"})

        # НЕ сбрасываем need_download - пользователь может скачивать файл многократно
        # session['need_download'] = False  # УБРАНО: позволяем повторные скачивания

        # Возвращаем найденный файл
        return FileResponse(path=file_path, filename=file_metadata.get('filename', ''), media_type=file_metadata.get('content_type', ''))

    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Unexpected file download error for File ID `{file_metadata.get('file_id', '')}`: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, {"code": "internal_server_error", "detail": "Произошла ошибка. Пожалуйста, попробуйте позже."})


@router.post("/session/reset")
async def reset_session(request: Request) -> JSONResponse:
    """
    Сброс сессии пользователя и очистка всех данных о файлах.
    Удаляет временные файлы и подготавливает сессию для новой загрузки.
    
    :param request: Объект запроса FastAPI
    :return: JSON с подтверждением сброса
    """
    logger.info("Session reset requested.")
    
    try:
        session = request.state.session.get_session()
        
        # Удаляем временный файл если он есть
        file_metadata = session.get('last_uploaded_file', {})
        if file_metadata:
            file_path = file_metadata.get('file_path', '')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"File removed during session reset: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove file during session reset: {e}")
        
        # Очищаем все флаги и данные сессии
        session['pending'] = False
        session['need_download'] = False
        session['last_uploaded_file'] = None
        
        logger.info("Session reset completed successfully")
        
        return JSONResponse(
            {"code": "success", "detail": "Сессия успешно сброшена"},
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error resetting session: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, {"code": "internal_server_error", "detail": "Ошибка сброса сессии"})


@router.post("/upload/stream")
async def upload_file_stream(
    file: UploadFile,
    request: Request,
    captcha_token: str = Form(None, alias="captcha_token")
) -> StreamingResponse:
    """
    Универсальная загрузка файла с SSE streaming прогресса.
    POST запрос сразу возвращает SSE поток.
    
    Архитектура:
    1. Валидация сессии
    2. Сохранение файла в temp директорию
    3. Прямой вызов ML сервиса через execute_stream() - БЕЗ RabbitMQ
    4. Проксирование SSE событий от сервиса к клиенту
    5. Сохранение метаданных в сессию
    
    Отправляет события:
    - event: progress - промежуточный прогресс от сервиса
    - event: complete - успешное завершение
    - event: error - ошибка обработки
    """
    logger.info(f"SSE upload started: {file.filename}")
    
    # Проверяем капчу перед началом стриминга
    from src.utils.captcha_utils import verify_captcha, get_client_ip
    
    client_ip = get_client_ip(request)
    is_captcha_valid = await verify_captcha(captcha_token or "", client_ip)
    
    if not is_captcha_valid:
        logger.warning(f"Captcha verification failed for SSE upload from IP: {client_ip}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CAPTCHA_FAILED",
                "detail": "Проверка капчи не пройдена. Пожалуйста, попробуйте снова."
            }
        )
    
    async def event_generator():
        session = None
        completed_successfully = False
        temp_file_path = None
        file_id = None
        
        file_service = FileUploadService()
        formatter = SSEEventFormatter()
        
        try:
            # Получаем сессию
            session = request.state.session.get_session()
            
            # 1. Валидация состояния сессии
            validation_error = file_service.validate_session_state(session)
            if validation_error:
                error_code, error_message = validation_error.split(":", 1)
                error_msg = {
                    "progress": -1,
                    "stage": "error",
                    "status": "error",
                    "error": {
                        "code": error_code,
                        "message": error_message,
                        "stage_failed": "validation",
                        "recoverable": True
                    }
                }
                yield formatter.format_event(error_msg)
                return
            
            # Устанавливаем pending только после успешной валидации
            session['pending'] = True
            
            # 2. Сохранение файла
            file_id, temp_file_path = await file_service.save_uploaded_file(file, session)
            
            # 3. Очистка предыдущих файлов
            await file_service.cleanup_previous_file(session)
            
            # 4. ПРЯМОЙ вызов ML сервиса через SSE registry (БЕЗ RabbitMQ!)
            file_name_without_ext = os.path.splitext(file.filename)[0] if file.filename else file_id
            
            logger.info(f"Starting ML service stream for: {file.filename}")
            
            # Проксируем все SSE события от ML сервиса напрямую
            async for sse_event in sse_registry.execute_service_stream(
                service_name="ml",
                params={
                    "data": {
                        "name": file_name_without_ext,
                        "path": temp_file_path
                    }
                }
            ):
                # Проверяем успешное завершение
                if 'event: complete' in sse_event:
                    completed_successfully = True
                
                yield sse_event
                await asyncio.sleep(0)
            
            # 5. Сохранение метаданных
            if completed_successfully:
                file_service.save_file_metadata(
                    session=session,
                    file_id=file_id,
                    filename=file.filename,
                    file_path=temp_file_path,
                    content_type=file.content_type,
                    size=file.size
                )
                
                session['pending'] = False
                session['need_download'] = True
                
                logger.info(f"SSE upload completed successfully: {file.filename}")
                
        except Exception as e:
            logger.error(f"Critical error in SSE upload: {e}", exc_info=True)
            
            # Cleanup при критической ошибке
            if session:
                session['pending'] = False
                session['need_download'] = False
                if temp_file_path:
                    await file_service.cleanup_temp_file(temp_file_path, session)
            
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Критическая ошибка сервера",
                    "stage_failed": "streaming",
                    "error_details": str(e)
                }
            }
            yield formatter.format_event(error_msg)
            
        finally:
            # КРИТИЧЕСКИ ВАЖНО: Cleanup при разрыве SSE соединения
            if session and not completed_successfully:
                if session.get('pending', False):
                    logger.warning(f"SSE connection interrupted for file {file.filename}")
                    
                    session['pending'] = False
                    
                    # Удаляем файл только если обработка не завершена
                    if not session.get('need_download', False) and temp_file_path:
                        await file_service.cleanup_temp_file(temp_file_path, session)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )