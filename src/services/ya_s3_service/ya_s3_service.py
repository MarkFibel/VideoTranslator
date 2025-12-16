"""
Сервис для работы с Yandex Object Storage через S3-совместимый API (aioboto3).

Поддерживаемые операции:
- upload: Загрузка файлов (с автоматическим переключением на multipart для больших файлов)
- download: Скачивание файлов
- delete: Удаление файлов из хранилища
- list: Список файлов в бакете

Автоматически регистрируется в RPC диспетчере как ya_s3.execute
"""

import logging
import os
import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime, timezone
import hashlib

import aioboto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig

from src.services.base_service import BaseService
from src.config.services.ya_s3_config import settings

logger = logging.getLogger(__name__)


class YaS3Service(BaseService):
    """
    Сервис для работы с Yandex Object Storage через S3-совместимый API.
    
    Реализует операции загрузки, скачивания и удаления файлов
    с использованием aioboto3 (async boto3 клиент для S3).
    
    Особенности:
    - Автоматическая multipart загрузка для файлов > YA_S3_MULTIPART_THRESHOLD_MB
    - Поддержка повторных попыток при сетевых ошибках
    - SSE прогресс для длительных операций
    - Проверка целостности файлов (MD5 хеши)
    """
    
    # Маппинг S3 ошибок в понятные сообщения
    S3_ERROR_CODES = {
        "NoSuchBucket": "Бакет не существует",
        "NoSuchKey": "Файл не найден в хранилище",
        "AccessDenied": "Доступ запрещен. Проверьте права доступа",
        "InvalidAccessKeyId": "Неверный Access Key ID",
        "SignatureDoesNotMatch": "Неверный Secret Access Key",
        "BucketAlreadyExists": "Бакет с таким именем уже существует",
        "BucketNotEmpty": "Невозможно удалить непустой бакет",
        "EntityTooLarge": "Файл слишком большой",
        "InvalidBucketName": "Неверное имя бакета",
        "KeyTooLong": "Слишком длинное имя файла",
        "ServiceUnavailable": "Сервис временно недоступен",
        "RequestTimeout": "Таймаут запроса"
    }
    
    def __init__(self):
        """Инициализация сервиса."""
        super().__init__()
        self._session: Optional[aioboto3.Session] = None
        self._boto_config: Optional[BotoConfig] = None
        
        # Настройка boto3 конфигурации с повторными попытками
        self._boto_config = BotoConfig(
            region_name=settings.YA_S3_REGION_NAME,
            signature_version='s3v4',  # AWS Signature Version 4 для Yandex Cloud
            s3={
                'addressing_style': 'virtual'  # Виртуальный стиль хостинга (bucket.storage.yandexcloud.net)
            },
            retries={
                'max_attempts': settings.YA_S3_MAX_RETRIES,
                'mode': 'adaptive'
            },
            connect_timeout=30,
            read_timeout=settings.YA_S3_OPERATION_TIMEOUT_SECONDS
        )
        
        logger.info("YaS3Service initialized with aioboto3")
    
    def _get_session(self) -> aioboto3.Session:
        """
        Возвращает aioboto3 сессию для работы с S3.
        
        :return: Aioboto3 сессия
        """
        if self._session is None:
            self._session = aioboto3.Session(
                aws_access_key_id=settings.YA_S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.YA_S3_SECRET_ACCESS_KEY,
                region_name=settings.YA_S3_REGION_NAME
            )
        return self._session
    
    def _get_s3_client(self):
        """
        Создает async S3 клиент (возвращает context manager).
        
        :return: Async context manager для S3 клиента
        """
        session = self._get_session()
        return session.client(
            's3',
            endpoint_url=settings.YA_S3_ENDPOINT_URL,
            config=self._boto_config
        )
    
    def _calculate_md5(self, file_path: Path) -> str:
        """
        Вычисляет MD5 хеш файла.
        
        :param file_path: Путь к файлу
        :return: MD5 хеш в hex формате
        """
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def _handle_s3_error(self, error: Exception, operation: str) -> str:
        """
        Обрабатывает ошибки S3 и возвращает понятное сообщение.
        
        :param error: Исключение
        :param operation: Название операции
        :return: Понятное сообщение об ошибке
        """
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_message = self.S3_ERROR_CODES.get(error_code, f"Ошибка S3: {error_code}")
            logger.error(f"S3 ClientError during {operation}: {error_code} - {error_message}")
            return f"{operation}: {error_message}"
        elif isinstance(error, BotoCoreError):
            logger.error(f"BotoCoreError during {operation}: {str(error)}")
            return f"{operation}: Ошибка соединения с S3"
        else:
            logger.error(f"Unexpected error during {operation}: {str(error)}")
            return f"{operation}: {str(error)}"
    
    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        SSE streaming выполнение операции с прогрессом.
        
        :param data: Словарь с параметрами операции:
            {
                "operation": "upload" | "download" | "delete" | "list",
                "file_path": str (для upload/download),
                "object_key": str (для download/delete),
                "prefix": str (для list, опционально)
            }
        :yield: Словари с SSE сообщениями (прогресс, ошибки, результаты)
        """
        self._start_tracking()
        
        # Извлекаем данные операции (поддерживаем оба формата: с вложенностью и без)
        operation_data = data.get("data", data)
        operation = operation_data.get("operation", "").lower()
        
        logger.info(f"YaS3Service.execute_stream: operation={operation}, data={operation_data}")
        
        # Валидация операции
        if not operation:
            yield self.create_error_message(
                error_code="OPERATION_MISSING",
                error_message="Не указана операция (operation)",
                stage_failed="validation"
            )
            return
        
        if operation not in ["upload", "download", "delete", "list"]:
            yield self.create_error_message(
                error_code="OPERATION_UNKNOWN",
                error_message=f"Неизвестная операция: {operation}",
                stage_failed="validation"
            )
            return
        
        try:
            # Маршрутизация на конкретный метод
            if operation == "upload":
                async for message in self._execute_upload_stream(operation_data):
                    yield message
            elif operation == "download":
                async for message in self._execute_download_stream(operation_data):
                    yield message
            elif operation == "delete":
                async for message in self._execute_delete_stream(operation_data):
                    yield message
            elif operation == "list":
                async for message in self._execute_list_stream(operation_data):
                    yield message
                    
        except Exception as e:
            error_msg = self._handle_s3_error(e, operation)
            logger.exception(f"Error in execute_stream for operation {operation}")
            yield self.create_error_message(
                error_code="SERVICE_ERROR",
                error_message=error_msg,
                stage_failed=operation,
                error_details=str(e)
            )
    
    async def _execute_upload_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Загружает файл в S3 с прогрессом.
        
        :param data: Параметры загрузки (file_path, object_key опционально)
        :yield: SSE сообщения с прогрессом
        """
        file_path_str = data.get("file_path")
        object_key = data.get("object_key")
        
        if not file_path_str:
            yield self.create_error_message(
                error_code="FILE_PATH_MISSING",
                error_message="Не указан путь к файлу (file_path)",
                stage_failed="validation"
            )
            return
        
        file_path = Path(file_path_str)
        if not file_path.exists():
            yield self.create_error_message(
                error_code="FILE_NOT_FOUND",
                error_message=f"Файл не найден: {file_path}",
                stage_failed="validation"
            )
            return
        
        # Если не указан object_key, используем имя файла
        if not object_key:
            object_key = file_path.name
        
        file_size = file_path.stat().st_size
        
        # Начинаем первую стадию
        self.next_stage()
        yield self.get_current_stage_message()
        
        logger.info(f"Starting upload: {file_path} -> s3://{settings.YA_S3_BUCKET_NAME}/{object_key} ({file_size} bytes)")
        
        try:
            # Вычисляем MD5 для проверки целостности
            md5_hash = self._calculate_md5(file_path)
            logger.info(f"File MD5: {md5_hash}")
            
            # Переходим к стадии загрузки
            self.next_stage()
            
            # Выбираем метод загрузки: simple или multipart
            if file_size > settings.multipart_threshold_bytes:
                logger.info(f"File size {file_size} exceeds threshold, using multipart upload")
                async for message in self._upload_file_multipart(file_path, object_key, file_size):
                    yield message
            else:
                logger.info(f"File size {file_size} below threshold, using simple upload")
                async for message in self._upload_file_simple(file_path, object_key, file_size):
                    yield message
            
            # Завершаем успешно
            public_url = settings.get_public_url(object_key)
            result = {
                "object_key": object_key,
                "bucket": settings.YA_S3_BUCKET_NAME,
                "size": file_size,
                "md5": md5_hash,
                "public_url": public_url,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            
            yield self.create_success_message(result=result)
            logger.info(f"Upload completed successfully: {object_key}")
            
        except Exception as e:
            error_msg = self._handle_s3_error(e, "upload")
            logger.exception(f"Upload failed for {file_path}")
            yield self.create_error_message(
                error_code="UPLOAD_FAILED",
                error_message=error_msg,
                stage_failed="uploading",
                error_details=str(e)
            )
    
    async def _upload_file_simple(self, file_path: Path, object_key: str, file_size: int) -> AsyncIterator[dict]:
        """
        Простая загрузка файла в S3 (для файлов < threshold).
        
        :param file_path: Путь к файлу
        :param object_key: Ключ объекта в S3
        :param file_size: Размер файла
        :yield: SSE сообщения с прогрессом
        """
        async with self._get_s3_client() as s3_client:
            with open(file_path, 'rb') as file_obj:
                await s3_client.put_object(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Key=object_key,
                    Body=file_obj
                )
                
                # Отправляем прогресс
                yield self.get_current_stage_message()
    
    async def _upload_file_multipart(self, file_path: Path, object_key: str, file_size: int) -> AsyncIterator[dict]:
        """
        Multipart загрузка файла в S3 (для больших файлов).
        
        :param file_path: Путь к файлу
        :param object_key: Ключ объекта в S3
        :param file_size: Размер файла
        :yield: SSE сообщения с прогрессом
        """
        chunk_size = settings.multipart_chunk_size_bytes
        total_parts = (file_size + chunk_size - 1) // chunk_size
        
        # Устанавливаем количество субшагов для прогресса
        self.next_stage(total_substeps=total_parts)
        
        async with self._get_s3_client() as s3_client:
            # Инициируем multipart upload
            response = await s3_client.create_multipart_upload(
                Bucket=settings.YA_S3_BUCKET_NAME,
                Key=object_key
            )
            upload_id = response['UploadId']
            logger.info(f"Multipart upload initiated: upload_id={upload_id}, total_parts={total_parts}")
            
            try:
                parts = []
                
                with open(file_path, 'rb') as file_obj:
                    for part_number in range(1, total_parts + 1):
                        # Читаем часть файла
                        chunk = file_obj.read(chunk_size)
                        
                        # Загружаем часть
                        part_response = await s3_client.upload_part(
                            Bucket=settings.YA_S3_BUCKET_NAME,
                            Key=object_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=chunk
                        )
                        
                        parts.append({
                            'PartNumber': part_number,
                            'ETag': part_response['ETag']
                        })
                        
                        # Обновляем прогресс
                        self.increment_substep()
                        yield self.get_current_stage_message(include_eta=True)
                        
                        logger.debug(f"Uploaded part {part_number}/{total_parts}")
                
                # Завершаем multipart upload
                await s3_client.complete_multipart_upload(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Key=object_key,
                    UploadId=upload_id,
                    MultipartUpload={'Parts': parts}
                )
                
                logger.info(f"Multipart upload completed: {object_key}")
                
            except Exception as e:
                # При ошибке отменяем multipart upload
                logger.error(f"Multipart upload failed, aborting: {e}")
                try:
                    await s3_client.abort_multipart_upload(
                        Bucket=settings.YA_S3_BUCKET_NAME,
                        Key=object_key,
                        UploadId=upload_id
                    )
                except Exception as abort_error:
                    logger.error(f"Failed to abort multipart upload: {abort_error}")
                raise
    
    async def _execute_download_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Скачивает файл из S3 с прогрессом.
        
        :param data: Параметры скачивания (object_key, download_path опционально)
        :yield: SSE сообщения с прогрессом
        """
        object_key = data.get("object_key")
        download_path_str = data.get("download_path")
        
        if not object_key:
            yield self.create_error_message(
                error_code="OBJECT_KEY_MISSING",
                error_message="Не указан ключ объекта (object_key)",
                stage_failed="validation"
            )
            return
        
        # Если не указан путь для скачивания, используем temp директорию
        if not download_path_str:
            temp_dir = Path(os.getenv("TEMP_DIR", "var/temp"))
            temp_dir.mkdir(parents=True, exist_ok=True)
            download_path = temp_dir / Path(object_key).name
        else:
            download_path = Path(download_path_str)
        
        # Начинаем первую стадию
        self.next_stage()
        yield self.get_current_stage_message()
        
        logger.info(f"Starting download: s3://{settings.YA_S3_BUCKET_NAME}/{object_key} -> {download_path}")
        
        try:
            async with self._get_s3_client() as s3_client:
                # Получаем метаданные объекта
                head_response = await s3_client.head_object(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Key=object_key
                )
                file_size = head_response['ContentLength']
                
                logger.info(f"Object size: {file_size} bytes")
                
                # Переходим к стадии скачивания
                self.next_stage()
                yield self.get_current_stage_message()
                
                # Скачиваем файл
                download_path.parent.mkdir(parents=True, exist_ok=True)
                
                await s3_client.download_file(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Key=object_key,
                    Filename=str(download_path)
                )
                
                logger.info(f"Download completed: {download_path}")
                
                # Завершаем успешно
                result = {
                    "object_key": object_key,
                    "download_path": str(download_path),
                    "size": file_size,
                    "downloaded_at": datetime.now(timezone.utc).isoformat()
                }
                
                yield self.create_success_message(result=result)
                
        except Exception as e:
            error_msg = self._handle_s3_error(e, "download")
            logger.exception(f"Download failed for {object_key}")
            yield self.create_error_message(
                error_code="DOWNLOAD_FAILED",
                error_message=error_msg,
                stage_failed="downloading",
                error_details=str(e)
            )
    
    async def _execute_delete_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Удаляет файл из S3.
        
        :param data: Параметры удаления (object_key)
        :yield: SSE сообщения с прогрессом
        """
        object_key = data.get("object_key")
        
        if not object_key:
            yield self.create_error_message(
                error_code="OBJECT_KEY_MISSING",
                error_message="Не указан ключ объекта (object_key)",
                stage_failed="validation"
            )
            return
        
        # Начинаем стадию удаления
        self.next_stage()
        yield self.get_current_stage_message()
        
        logger.info(f"Deleting object: s3://{settings.YA_S3_BUCKET_NAME}/{object_key}")
        
        try:
            async with self._get_s3_client() as s3_client:
                await s3_client.delete_object(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Key=object_key
                )
                
                logger.info(f"Object deleted: {object_key}")
                
                result = {
                    "object_key": object_key,
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }
                
                yield self.create_success_message(result=result)
                
        except Exception as e:
            error_msg = self._handle_s3_error(e, "delete")
            logger.exception(f"Delete failed for {object_key}")
            yield self.create_error_message(
                error_code="DELETE_FAILED",
                error_message=error_msg,
                stage_failed="deleting",
                error_details=str(e)
            )
    
    async def _execute_list_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Получает список файлов из S3.
        
        :param data: Параметры (prefix опционально)
        :yield: SSE сообщения с прогрессом
        """
        prefix = data.get("prefix", "")
        
        # Начинаем стадию получения списка
        self.next_stage()
        yield self.get_current_stage_message()
        
        logger.info(f"Listing objects in bucket {settings.YA_S3_BUCKET_NAME} with prefix '{prefix}'")
        
        try:
            async with self._get_s3_client() as s3_client:
                paginator = s3_client.get_paginator('list_objects_v2')
                
                objects = []
                async for page in paginator.paginate(
                    Bucket=settings.YA_S3_BUCKET_NAME,
                    Prefix=prefix
                ):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            objects.append({
                                "key": obj['Key'],
                                "size": obj['Size'],
                                "last_modified": obj['LastModified'].isoformat(),
                                "etag": obj['ETag'].strip('"')
                            })
                
                logger.info(f"Found {len(objects)} objects")
                
                result = {
                    "bucket": settings.YA_S3_BUCKET_NAME,
                    "prefix": prefix,
                    "count": len(objects),
                    "objects": objects
                }
                
                yield self.create_success_message(result=result)
                
        except Exception as e:
            error_msg = self._handle_s3_error(e, "list")
            logger.exception(f"List failed for prefix '{prefix}'")
            yield self.create_error_message(
                error_code="LIST_FAILED",
                error_message=error_msg,
                stage_failed="listing",
                error_details=str(e)
            )
    
    async def execute(self, data: dict) -> dict:
        """
        :return: Результат выполнения (последнее сообщение из потока)
        """
        logger.info(f"YaS3Service.execute() called with data: {data}")
        
        messages = []
        async for message in self.execute_stream(data):
            messages.append(message)
        
        # Возвращаем последнее сообщение (обычно success или error)
        return messages[-1] if messages else {"status": "error", "message": "No response"}

