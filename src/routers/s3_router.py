"""
Роутер для работы с Yandex Object Storage S3 через SSE.

Использует универсальную SSE архитектуру с прямым вызовом сервисов.
"""

import logging
import os
import tempfile
from fastapi import APIRouter, File, UploadFile, Form, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from src.utils.sse_service_registry import sse_registry
from src.utils.sse_formatter import SSEEventFormatter
from src.utils.sse_utils import get_sse_headers
from src.services.ya_s3_service.ya_s3_service import YaS3Service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/s3", tags=["s3"])

# Создаем экземпляр сервиса для генерации presigned URL
_s3_service = YaS3Service()


@router.get("/presigned-url")
async def get_presigned_url(
    object_key: str = Query(..., description="Ключ объекта в S3"),
    expiration_hours: Optional[int] = Query(None, description="Время жизни URL в часах")
) -> JSONResponse:
    """
    Генерирует presigned URL для скачивания файла из S3.
    
    Presigned URL позволяет скачивать приватные файлы без авторизации
    в течение указанного времени.
    
    :param object_key: Ключ объекта в S3 (путь к файлу в бакете)
    :param expiration_hours: Время жизни URL в часах (по умолчанию из настроек YA_S3_SIGNED_URL_EXPIRATION_HOURS)
    :return: JSON с presigned URL
    """
    logger.info(f"Generating presigned URL for: {object_key}")
    
    try:
        presigned_url = await _s3_service.generate_presigned_url(
            object_key=object_key,
            expiration_hours=expiration_hours
        )
        
        from src.config.services.ya_s3_config import settings
        expires_in = expiration_hours or settings.YA_S3_SIGNED_URL_EXPIRATION_HOURS
        
        return JSONResponse({
            "object_key": object_key,
            "download_url": presigned_url,
            "expires_in_hours": expires_in
        })
        
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {object_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PRESIGNED_URL_GENERATION_FAILED",
                "message": f"Не удалось сгенерировать URL для скачивания: {str(e)}"
            }
        )


@router.post("/stream")
async def s3_operation_stream(
    request: Request,
    operation: str = Form(...),
    file: Optional[UploadFile] = File(None),
    object_key: Optional[str] = Form(None),
    content_type: Optional[str] = Form(None),
    destination_path: Optional[str] = Form(None),
    version_id: Optional[str] = Form(None)
):
    """
    Универсальный SSE endpoint для операций с Yandex Object Storage.
    
    Использует прямой вызов ya_s3 сервиса БЕЗ RabbitMQ.
    
    Поддерживаемые операции:
    - upload: Загрузка файла в S3
    - download: Скачивание файла из S3
    - delete: Удаление файла из S3
    
    :param operation: Тип операции (upload/download/delete)
    :param file: Файл для загрузки (для upload)
    :param object_key: Ключ объекта в S3
    :param content_type: MIME тип файла (для upload)
    :param destination_path: Путь для сохранения (для download)
    :param version_id: ID версии (для delete с версионированием)
    """
    logger.info(f"S3 SSE operation request: {operation}")
    
    # Сохраняем operation в локальной переменной для использования в генераторе
    op = operation
    
    async def event_generator():
        temp_file_path = None
        completed_successfully = False
        formatter = SSEEventFormatter()
        
        try:
            # Формируем параметры для сервиса
            service_params = {
                "operation": op
            }
            
            # Обработка разных операций
            if op == "upload":
                if not file:
                    error_msg = {
                        "progress": -1,
                        "stage": "error",
                        "status": "error",
                        "error": {
                            "code": "MISSING_FILE",
                            "message": "Файл не предоставлен для загрузки",
                            "stage_failed": "validation",
                            "recoverable": True
                        }
                    }
                    yield formatter.format_event(error_msg)
                    return
                
                # Сохраняем файл временно
                temp_dir = "var/temp"
                os.makedirs(temp_dir, exist_ok=True)
                
                filename = file.filename or "uploaded_file"
                temp_file_path = os.path.join(temp_dir, filename)
                with open(temp_file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                
                logger.info(f"File saved temporarily: {temp_file_path} ({len(content)} bytes)")
                
                service_params["file_path"] = temp_file_path
                if object_key:
                    service_params["object_key"] = object_key
                if content_type:
                    service_params["content_type"] = content_type
            
            elif op == "download":
                if not object_key:
                    error_msg = {
                        "progress": -1,
                        "stage": "error",
                        "status": "error",
                        "error": {
                            "code": "MISSING_OBJECT_KEY",
                            "message": "Не указан ключ объекта для скачивания",
                            "stage_failed": "validation",
                            "recoverable": True
                        }
                    }
                    yield formatter.format_event(error_msg)
                    return
                
                service_params["object_key"] = object_key
                service_params["destination_path"] = destination_path or object_key
            
            elif op == "delete":
                if not object_key:
                    error_msg = {
                        "progress": -1,
                        "stage": "error",
                        "status": "error",
                        "error": {
                            "code": "MISSING_OBJECT_KEY",
                            "message": "Не указан ключ объекта для удаления",
                            "stage_failed": "validation",
                            "recoverable": True
                        }
                    }
                    yield formatter.format_event(error_msg)
                    return
                
                service_params["object_key"] = object_key
                if version_id:
                    service_params["version_id"] = version_id
            
            else:
                error_msg = {
                    "progress": -1,
                    "stage": "error",
                    "status": "error",
                    "error": {
                        "code": "INVALID_OPERATION",
                        "message": f"Неизвестная операция: {op}",
                        "stage_failed": "validation",
                        "recoverable": True
                    }
                }
                yield formatter.format_event(error_msg)
                return
            
            # ПРЯМОЙ вызов ya_s3 сервиса через SSE registry (БЕЗ RabbitMQ!)
            logger.info(f"Starting ya_s3 service stream with params: {service_params}")
            
            async for sse_event in sse_registry.execute_service_stream(
                service_name="ya_s3",
                params={"data": service_params}
            ):
                # Проверяем успешное завершение
                if 'event: complete' in sse_event:
                    completed_successfully = True
                
                yield sse_event
                
                # Если ошибка - всё равно продолжаем (событие уже отправлено)
                if 'event: error' in sse_event:
                    break
        
        except Exception as e:
            logger.error(f"Critical error in S3 operation: {e}", exc_info=True)
            
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Внутренняя ошибка сервера",
                    "stage_failed": "execution",
                    "error_details": str(e),
                    "recoverable": False
                }
            }
            yield formatter.format_event(error_msg)
        
        finally:
            # Очищаем временный файл при загрузке
            if op == "upload" and temp_file_path:
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        logger.info(f"Temporary file removed: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Failed to remove temporary file: {e}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )
