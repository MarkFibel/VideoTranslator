"""
Роутер для работы с Yandex Object Storage S3.

Использует RabbitMQ для вызова ya_s3 сервиса в воркере.
SSE пинги поддерживают соединение пока идёт операция.
"""

import logging
import os
import asyncio
from fastapi import APIRouter, File, UploadFile, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from src.transport.rabbitmq.producer import RPCProducer
from src.utils.sse_formatter import SSEEventFormatter
from src.utils.sse_utils import get_sse_headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/s3", tags=["s3"])

# Константы
RPC_TIMEOUT = 900.0  # 15 минут
SSE_PING_INTERVAL = 15  # секунд


@router.post("/upload")
async def s3_upload(
    request: Request,
    file: UploadFile = File(...),
    object_key: Optional[str] = Form(None),
    content_type: Optional[str] = Form(None)
) -> StreamingResponse:
    """
    Загрузка файла в S3 через RabbitMQ с SSE пингами.
    
    :param file: Файл для загрузки
    :param object_key: Ключ объекта в S3 (если не указан - используется имя файла)
    :param content_type: MIME тип файла
    """
    logger.info(f"S3 upload request: {file.filename}")
    
    async def event_generator():
        temp_file_path = None
        producer = None
        formatter = SSEEventFormatter()
        
        try:
            # 1. Сохраняем файл временно
            temp_dir = "var/temp"
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file_path = os.path.join(temp_dir, file.filename or "upload")
            with open(temp_file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            logger.info(f"File saved temporarily: {temp_file_path} ({len(content)} bytes)")
            
            # 2. Подключаемся к RabbitMQ
            producer = RPCProducer()
            await producer.connect()
            
            # 3. Формируем параметры
            final_object_key = object_key or f"uploads/{file.filename}"
            
            service_params = {
                "operation": "upload",
                "file_path": temp_file_path,
                "object_key": final_object_key
            }
            if content_type:
                service_params["content_type"] = content_type
            
            # 4. Отправляем задачу в очередь
            logger.info(f"Starting S3 upload via RabbitMQ: {final_object_key}")
            
            yield formatter.format_ping()
            
            task = asyncio.create_task(
                producer.call(
                    method="ya_s3.execute",
                    params={"data": service_params},
                    timeout=RPC_TIMEOUT
                )
            )
            
            # 5. Ждём с пингами
            while not task.done():
                yield formatter.format_ping()
                await asyncio.sleep(SSE_PING_INTERVAL)
            
            # 6. Получаем результат
            result = await task
            logger.info(f"S3 upload completed: {result}")
            
            complete_msg = {
                "progress": 100,
                "stage": "complete",
                "status": "completed",
                "result": result
            }
            yield formatter.format_event(complete_msg, event_type="complete")
            
        except Exception as e:
            logger.error(f"S3 upload error: {e}", exc_info=True)
            
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "S3_UPLOAD_ERROR",
                    "message": str(e),
                    "stage_failed": "upload",
                    "recoverable": True
                }
            }
            yield formatter.format_event(error_msg)
            
        finally:
            if producer:
                try:
                    await producer.close()
                except Exception:
                    pass
            
            # Очищаем временный файл
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Temporary file removed: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Failed to remove temp file: {e}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )


@router.post("/download")
async def s3_download(
    request: Request,
    object_key: str = Form(...),
    destination_path: Optional[str] = Form(None)
) -> StreamingResponse:
    """
    Скачивание файла из S3 через RabbitMQ с SSE пингами.
    
    :param object_key: Ключ объекта в S3
    :param destination_path: Путь для сохранения файла
    """
    logger.info(f"S3 download request: {object_key}")
    
    async def event_generator():
        producer = None
        formatter = SSEEventFormatter()
        
        try:
            producer = RPCProducer()
            await producer.connect()
            
            service_params = {
                "operation": "download",
                "object_key": object_key,
                "destination_path": destination_path or object_key
            }
            
            logger.info(f"Starting S3 download via RabbitMQ: {object_key}")
            
            yield formatter.format_ping()
            
            task = asyncio.create_task(
                producer.call(
                    method="ya_s3.execute",
                    params={"data": service_params},
                    timeout=RPC_TIMEOUT
                )
            )
            
            while not task.done():
                yield formatter.format_ping()
                await asyncio.sleep(SSE_PING_INTERVAL)
            
            result = await task
            logger.info(f"S3 download completed: {result}")
            
            complete_msg = {
                "progress": 100,
                "stage": "complete",
                "status": "completed",
                "result": result
            }
            yield formatter.format_event(complete_msg, event_type="complete")
            
        except Exception as e:
            logger.error(f"S3 download error: {e}", exc_info=True)
            
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "S3_DOWNLOAD_ERROR",
                    "message": str(e),
                    "stage_failed": "download",
                    "recoverable": True
                }
            }
            yield formatter.format_event(error_msg)
            
        finally:
            if producer:
                try:
                    await producer.close()
                except Exception:
                    pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )


@router.post("/delete")
async def s3_delete(
    request: Request,
    object_key: str = Form(...),
    version_id: Optional[str] = Form(None)
) -> JSONResponse:
    """
    Удаление файла из S3 через RabbitMQ.
    Синхронный endpoint - удаление обычно быстрое.
    
    :param object_key: Ключ объекта в S3
    :param version_id: ID версии (для версионированных бакетов)
    """
    logger.info(f"S3 delete request: {object_key}")
    
    producer = None
    
    try:
        producer = RPCProducer()
        await producer.connect()
        
        service_params = {
            "operation": "delete",
            "object_key": object_key
        }
        if version_id:
            service_params["version_id"] = version_id
        
        result = await producer.call(
            method="ya_s3.execute",
            params={"data": service_params},
            timeout=60.0  # Удаление быстрое
        )
        
        logger.info(f"S3 delete completed: {result}")
        
        return JSONResponse({
            "code": "success",
            "detail": "Файл успешно удалён",
            "result": result
        })
        
    except Exception as e:
        logger.error(f"S3 delete error: {e}", exc_info=True)
        return JSONResponse({
            "code": "error",
            "detail": str(e)
        }, status_code=500)
        
    finally:
        if producer:
            try:
                await producer.close()
            except Exception:
                pass
