import os
import uuid
from datetime import datetime, timezone
import logging
from starlette.status   import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi            import APIRouter, HTTPException, UploadFile, Request
from fastapi.responses  import FileResponse, JSONResponse

from src.transport.rabbitmq.producer import RPCProducer
from src.config.app_config import settings
from src.utils.files_utils import get_file_extension_by_content_type

router = APIRouter(prefix='/files', tags=["files"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    request: Request
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
            timeout=120.
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

        session['need_download'] = False

        # Возвращаем найденный файл
        return FileResponse(path=file_path, filename=file_metadata.get('filename', ''), media_type=file_metadata.get('content_type', ''))

    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Unexpected file download error for File ID `{file_metadata.get('file_id', '')}`: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, {"code": "internal_server_error", "detail": "Произошла ошибка. Пожалуйста, попробуйте позже."})