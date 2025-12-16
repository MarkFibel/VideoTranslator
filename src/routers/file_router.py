"""
Роутер для работы с файлами.

Архитектура:
1. Клиент загружает файл через SSE endpoint
2. Файл сохраняется локально
3. Загружается в S3 через RabbitMQ (ya_s3.execute)
4. Отправляется на ML обработку через RabbitMQ (ml.execute)
5. SSE пинги поддерживают соединение пока идёт обработка
6. Результат возвращается клиенту
"""

import os
import asyncio
import logging
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi import APIRouter, HTTPException, UploadFile, Request, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from src.transport.rabbitmq.producer import RPCProducer
from src.utils.sse_utils import get_sse_headers
from src.utils.upload_utils import FileUploadService
from src.utils.sse_formatter import SSEEventFormatter

router = APIRouter(prefix='/files', tags=["files"])
logger = logging.getLogger(__name__)

# Константы
RPC_TIMEOUT = 900.0  # 15 минут
SSE_PING_INTERVAL = 15  # секунд


@router.get("/session/status")
async def get_session_status(request: Request) -> JSONResponse:
    """
    Получение статуса сессии пользователя.
    Возвращает информацию о текущем состоянии обработки файла.
    """
    logger.info("Session status requested.")
    
    try:
        session = request.state.session.get_session()
        
        pending = session.get('pending', False)
        need_download = session.get('need_download', False)
        file_metadata = session.get('last_uploaded_file', {})
        
        response_data = {
            "pending": pending,
            "need_download": need_download,
            "file": None
        }
        
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
    """
    logger.info("File download requested.")
    
    try:
        session = request.state.session.get_session()
        file_metadata = session.get('last_uploaded_file', {})
        
        file_path = file_metadata.get("file_path", "")
        logger.info(f"Looking for file with path: `{file_path}`")

        if not os.path.exists(file_path):
            logger.error(f"No files found for File ID: {file_metadata.get('file_id', '')}")
            raise HTTPException(404, {"code": "file_not_found", "detail": "Файл не найден"})

        return FileResponse(
            path=file_path, 
            filename=file_metadata.get('filename', ''), 
            media_type=file_metadata.get('content_type', '')
        )

    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Unexpected file download error: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, {"code": "internal_server_error", "detail": "Произошла ошибка. Пожалуйста, попробуйте позже."})


@router.post("/session/reset")
async def reset_session(request: Request) -> JSONResponse:
    """
    Сброс сессии пользователя и очистка всех данных о файлах.
    """
    logger.info("Session reset requested.")
    
    try:
        session = request.state.session.get_session()
        
        file_metadata = session.get('last_uploaded_file', {})
        if file_metadata:
            file_path = file_metadata.get('file_path', '')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"File removed during session reset: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove file during session reset: {e}")
        
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
    Загрузка файла с SSE streaming.
    
    Архитектура:
    1. Валидация сессии и капчи
    2. Сохранение файла локально
    3. Загрузка в S3 через RabbitMQ (ya_s3.execute)
    4. ML обработка через RabbitMQ (ml.execute)
    5. SSE пинги каждые 15 секунд пока идёт обработка
    6. Финальный ответ event: complete с URL результата
    
    Отправляет события:
    - event: ping - поддержание соединения
    - event: complete - успешное завершение с URL
    - event: error - ошибка обработки
    """
    logger.info(f"SSE upload started: {file.filename}")
    
    # Проверяем капчу
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
        producer = None
        
        file_service = FileUploadService()
        formatter = SSEEventFormatter()
        
        try:
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
            
            session['pending'] = True
            
            # 2. Сохранение файла локально
            file_id, temp_file_path = await file_service.save_uploaded_file(file, session)
            logger.info(f"File saved locally: {temp_file_path}")
            
            # 3. Очистка предыдущих файлов
            await file_service.cleanup_previous_file(session)
            
            # 4. Подключение к RabbitMQ
            producer = RPCProducer()
            await producer.connect()
            logger.info("RabbitMQ producer connected")
            
            # 5. Загрузка в S3 через RabbitMQ
            file_ext = temp_file_path.split('.')[-1] if '.' in temp_file_path else ''
            s3_object_key = f"uploads/{file_id}.{file_ext}" if file_ext else f"uploads/{file_id}"
            
            logger.info(f"Starting S3 upload via RabbitMQ: {s3_object_key}")
            
            # Отправляем пинг перед началом S3 загрузки
            yield formatter.format_ping()
            
            # Запускаем S3 загрузку в фоне с пингами
            s3_task = asyncio.create_task(
                producer.call(
                    method="ya_s3.execute",
                    params={
                        "data": {
                            "operation": "upload",
                            "file_path": temp_file_path,
                            "object_key": s3_object_key
                        }
                    },
                    timeout=RPC_TIMEOUT
                )
            )
            
            # Ждём завершения S3 с пингами
            s3_result = None
            while not s3_task.done():
                yield formatter.format_ping()
                await asyncio.sleep(SSE_PING_INTERVAL)
            
            # Получаем результат S3
            try:
                s3_result = await s3_task
                logger.info(f"S3 upload completed: {s3_result}")
            except Exception as s3_error:
                logger.error(f"S3 upload failed: {s3_error}", exc_info=True)
                error_msg = {
                    "progress": -1,
                    "stage": "error",
                    "status": "error",
                    "error": {
                        "code": "S3_UPLOAD_FAILED",
                        "message": "Ошибка загрузки файла в хранилище",
                        "stage_failed": "s3_upload",
                        "error_details": str(s3_error),
                        "recoverable": True
                    }
                }
                yield formatter.format_event(error_msg)
                return
            
            # 6. ML обработка через RabbitMQ
            file_name_without_ext = os.path.splitext(file.filename)[0] if file.filename else file_id
            
            logger.info(f"Starting ML processing via RabbitMQ: {file_name_without_ext}")
            
            # Запускаем ML обработку в фоне
            ml_task = asyncio.create_task(
                producer.call(
                    method="ml.execute",
                    params={
                        "data": {
                            "name": file_name_without_ext,
                            "path": temp_file_path
                        }
                    },
                    timeout=RPC_TIMEOUT
                )
            )
            
            # Ждём завершения ML с пингами
            while not ml_task.done():
                yield formatter.format_ping()
                await asyncio.sleep(SSE_PING_INTERVAL)
            
            # Получаем результат ML
            try:
                ml_result = await ml_task
                logger.info(f"ML processing completed: {ml_result}")
            except Exception as ml_error:
                logger.error(f"ML processing failed: {ml_error}", exc_info=True)
                error_msg = {
                    "progress": -1,
                    "stage": "error",
                    "status": "error",
                    "error": {
                        "code": "ML_PROCESSING_FAILED",
                        "message": "Ошибка обработки файла",
                        "stage_failed": "ml_processing",
                        "error_details": str(ml_error),
                        "recoverable": True
                    }
                }
                yield formatter.format_event(error_msg)
                return
            
            # 7. Успешное завершение
            completed_successfully = True
            
            # Сохраняем метаданные
            file_service.save_file_metadata(
                session=session,
                file_id=file_id,
                filename=file.filename or "unknown",
                file_path=temp_file_path,
                content_type=file.content_type or "application/octet-stream",
                size=file.size or 0
            )
            
            # Добавляем S3 URL в метаданные
            s3_url = s3_result.get('url') if isinstance(s3_result, dict) else None
            if s3_url:
                session['last_uploaded_file']['s3_url'] = s3_url
                session['last_uploaded_file']['s3_object_key'] = s3_object_key
            
            session['pending'] = False
            session['need_download'] = True
            
            # Отправляем complete событие
            complete_msg = {
                "progress": 100,
                "stage": "complete",
                "status": "completed",
                "result": {
                    "filename": file.filename,
                    "file_id": file_id,
                    "s3_url": s3_url,
                    "ml_result": ml_result
                }
            }
            yield formatter.format_event(complete_msg, event_type="complete")
            
            logger.info(f"SSE upload completed successfully: {file.filename}")
            
        except Exception as e:
            logger.error(f"Critical error in SSE upload: {e}", exc_info=True)
            
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
            # Закрываем producer
            if producer:
                try:
                    await producer.close()
                except Exception:
                    pass
            
            # Cleanup при разрыве соединения
            if session and not completed_successfully:
                if session.get('pending', False):
                    logger.warning(f"SSE connection interrupted for file {file.filename}")
                    session['pending'] = False
                    
                    if not session.get('need_download', False) and temp_file_path:
                        await file_service.cleanup_temp_file(temp_file_path, session)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )
