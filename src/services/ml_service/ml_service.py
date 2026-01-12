"""
Обертка сервиса перевода видео.

Логика работы:
1. Загрузить локальный файл в S3
2. Отправить download_url на удаленный ML сервис (SSE)
3. Проксировать SSE события от ML сервиса
4. Скачать результат из S3 в ту же папку
"""

import os
import logging
from pathlib import Path
from typing import AsyncIterator, Optional
from contextlib import contextmanager
from time import perf_counter
from urllib.parse import urlparse

import httpx
from httpx_sse import aconnect_sse

from src.services.base_service import BaseService
from src.services.ya_s3_service.ya_s3_service import YaS3Service
from src.config.services.ml_config import settings


@contextmanager
def log_duration(message: str):
    """Контекстный менеджер для логирования времени выполнения."""
    logger.info(f"⌛ {message}")
    start = perf_counter()
    yield
    end = perf_counter()
    logger.info(f"✅ {message} - Время выполнения: {end - start:.4f} сек")


logger = logging.getLogger(__name__)


class MLService(BaseService):
    """
    Обертка сервиса для обработки видео с применением ML-пайплайна.

    Этот класс выполняет:
    1. Загрузку локального файла в S3
    2. Вызов удаленного ML сервера с SSE streaming
    3. Проксирование SSE событий клиенту
    4. Скачивание результата из S3
    """

    # Маппинг прогресса для этапов
    PROGRESS_UPLOAD_START = 0
    PROGRESS_UPLOAD_END = 25
    PROGRESS_ML_START = 25
    PROGRESS_ML_END = 85
    PROGRESS_DOWNLOAD_START = 85
    PROGRESS_DOWNLOAD_END = 100

    def __init__(self):
        """Инициализация ML-сервиса."""
        super().__init__(settings)
        
        self.remote_url = settings.REMOTE_URL
        self.sse_remote_url = settings.SSE_REMOTE_URL
        self.sse_timeout = settings.sse_timeout
        self.synchronous_timeout = settings.synchronous_timeout
        self.connect_timeout = settings.connect_timeout
        
        # Инициализация S3 сервиса
        self._s3_service: Optional[YaS3Service] = None
        
        logger.info(f"MLService initialized. SSE URL: {self.sse_remote_url}")

    def _get_s3_service(self) -> YaS3Service:
        """Ленивая инициализация S3 сервиса."""
        if self._s3_service is None:
            self._s3_service = YaS3Service()
        return self._s3_service

    def _map_progress(self, source_progress: int, source_start: int, source_end: int, 
                      target_start: int, target_end: int) -> int:
        """
        Маппинг прогресса из одного диапазона в другой.
        
        :param source_progress: Исходный прогресс
        :param source_start: Начало исходного диапазона
        :param source_end: Конец исходного диапазона
        :param target_start: Начало целевого диапазона
        :param target_end: Конец целевого диапазона
        :return: Прогресс в целевом диапазоне
        """
        if source_end == source_start:
            return target_start
        
        ratio = (source_progress - source_start) / (source_end - source_start)
        return int(target_start + ratio * (target_end - target_start))

    def _extract_object_key_from_url(self, url: str) -> str:
        """
        Извлечь object_key из URL S3.
        
        :param url: Полный URL файла в S3
        :return: Ключ объекта
        """
        parsed = urlparse(url)
        # Путь начинается с /, убираем его
        path = parsed.path.lstrip('/')
        return path

    def execute(self, data: dict) -> dict:
        """
        Основной метод для вызова пайплайна обработки видео (синхронный).

        Args:
            data (dict): Входные данные с ключами:
                - "path" (str): Путь к локальному видео файлу.

        Returns:
            dict: Результат выполнения с ключами:
                - "status" (str): Статус выполнения ("success" или "error").
                - "message" (str): Сообщение о результате.
                - "result_path" (str): Путь к результирующему файлу.
        """
        logger.info(f"MLService.execute called with data: {data}")

        file_path = data.get("path")

        if not file_path:
            logger.error("❌ Путь к видео не указан")
            return {"status": "error", "message": "`path` missing"}

        if not self.remote_url:
            logger.error("❌ remote_url не настроен")
            return {"status": "error", "message": "remote_url not configured"}

        # Синхронный вызов - используем простой POST
        with log_duration("Синхронный вызов ML сервиса"):
            try:
                with httpx.Client(timeout=self.synchronous_timeout) as client:
                    response = client.post(
                        url=self.remote_url,
                        json={'path': file_path}
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    return {
                        "status": "success",
                        "message": "Processing completed",
                        "result": result,
                        "service": self.getName()
                    }
            except httpx.RequestError as e:
                logger.error(f"Ошибка при вызове ML сервиса: {e}")
                return {"status": "error", "message": str(e)}

    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Streaming версия execute() для SSE.
        
        Полный пайплайн:
        1. Upload файла в S3
        2. Вызов удаленного ML сервиса (SSE)
        3. Скачивание результата из S3
        
        Args:
            data (dict): Входные данные с ключами:
                - "path" (str): Путь к локальному видео файлу.
        
        Yields:
            dict: SSE сообщения о прогрессе
        """
        self._start_tracking()
        
        try:
            file_path_str = data.get("path")
            
            # Валидация входных данных
            if not file_path_str:
                yield self.create_error_message(
                    error_code="PATH_MISSING",
                    error_message="Не указан путь к файлу (path)",
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
            
            if not self.sse_remote_url:
                yield self.create_error_message(
                    error_code="CONFIG_ERROR",
                    error_message="sse_remote_url не настроен",
                    stage_failed="validation"
                )
                return
            
            # Сохраняем директорию исходного файла для результата
            result_directory = file_path.parent
            original_filename = file_path.stem
            
            logger.info(f"Starting ML pipeline for: {file_path}")
            
            # ========== ЭТАП 1: Upload в S3 ==========
            yield self.create_progress_message(
                progress=self.PROGRESS_UPLOAD_START,
                stage="uploading_to_s3",
                status="processing"
            )
            
            upload_result = None
            async for msg in self._upload_to_s3(file_path):
                if msg.get("status") == "error":
                    yield msg
                    return
                elif msg.get("status") == "success":
                    upload_result = msg.get("result", {})
                else:
                    # Маппинг прогресса загрузки (0-100) в (0-25)
                    if "progress" in msg:
                        mapped_progress = self._map_progress(
                            msg["progress"], 0, 100,
                            self.PROGRESS_UPLOAD_START, self.PROGRESS_UPLOAD_END
                        )
                        msg["progress"] = mapped_progress
                    yield msg
            
            if not upload_result:
                yield self.create_error_message(
                    error_code="UPLOAD_FAILED",
                    error_message="Не удалось получить результат загрузки в S3",
                    stage_failed="uploading_to_s3"
                )
                return
            
            download_url = upload_result.get("download_url")
            logger.info(f"File uploaded to S3: {download_url}")
            
            # Удаляем локальный файл после успешной загрузки
            try:
                file_path.unlink()
                logger.info(f"Local file deleted: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete local file: {e}")
            
            # ========== ЭТАП 2: Вызов ML сервиса ==========
            yield self.create_progress_message(
                progress=self.PROGRESS_ML_START,
                stage="ml_processing",
                status="processing"
            )
            
            ml_result = None
            async for msg in self._call_ml_service_sse(download_url):
                if msg.get("status") == "error":
                    yield msg
                    return
                elif msg.get("status") == "success":
                    ml_result = msg.get("result", {})
                else:
                    # Маппинг прогресса ML (0-100) в (25-85)
                    if "progress" in msg:
                        mapped_progress = self._map_progress(
                            msg["progress"], 0, 100,
                            self.PROGRESS_ML_START, self.PROGRESS_ML_END
                        )
                        msg["progress"] = mapped_progress
                    yield msg
            
            if not ml_result:
                yield self.create_error_message(
                    error_code="ML_PROCESSING_FAILED",
                    error_message="Не удалось получить результат от ML сервиса",
                    stage_failed="ml_processing"
                )
                return
            
            result_download_url = ml_result.get("download_url")
            if not result_download_url:
                yield self.create_error_message(
                    error_code="ML_RESULT_MISSING",
                    error_message="ML сервис не вернул download_url результата",
                    stage_failed="ml_processing"
                )
                return
            
            logger.info(f"ML processing completed. Result URL: {result_download_url}")
            
            # ========== ЭТАП 3: Скачивание результата ==========
            yield self.create_progress_message(
                progress=self.PROGRESS_DOWNLOAD_START,
                stage="downloading_result",
                status="processing"
            )
            
            # Извлекаем object_key из URL результата
            result_object_key = self._extract_object_key_from_url(result_download_url)
            
            # Формируем путь для скачивания (в ту же папку)
            result_filename = Path(result_object_key).name
            result_path = result_directory / result_filename
            
            download_result = None
            async for msg in self._download_from_s3(result_object_key, result_path):
                if msg.get("status") == "error":
                    yield msg
                    return
                elif msg.get("status") == "success":
                    download_result = msg.get("result", {})
                else:
                    # Маппинг прогресса скачивания (0-100) в (90-100)
                    if "progress" in msg:
                        mapped_progress = self._map_progress(
                            msg["progress"], 0, 100,
                            self.PROGRESS_DOWNLOAD_START, self.PROGRESS_DOWNLOAD_END
                        )
                        msg["progress"] = mapped_progress
                    yield msg
            
            if not download_result:
                yield self.create_error_message(
                    error_code="DOWNLOAD_FAILED",
                    error_message="Не удалось скачать результат из S3",
                    stage_failed="downloading_result"
                )
                return
            
            final_path = download_result.get("download_path", str(result_path))
            logger.info(f"Result downloaded to: {final_path}")
            
            # ========== УСПЕШНОЕ ЗАВЕРШЕНИЕ ==========
            yield self.create_success_message(
                result={
                    "path": final_path,
                    "original_file": file_path_str,
                    "s3_url": result_download_url
                }
            )

        except Exception as e:
            logger.exception("❌ Ошибка в execute_stream")
            yield self.create_error_message(
                error_code="ML_PROCESSING_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown"
            )

    async def _upload_to_s3(self, file_path: Path) -> AsyncIterator[dict]:
        """
        Загрузить файл в S3.
        
        :param file_path: Путь к локальному файлу
        :yield: SSE сообщения от S3 сервиса
        """
        s3_service = self._get_s3_service()
        
        upload_data = {
            "data": {
                "operation": "upload",
                "file_path": str(file_path)
            }
        }
        
        async for msg in s3_service.execute_stream(upload_data):
            yield msg

    async def _download_from_s3(self, object_key: str, download_path: Path) -> AsyncIterator[dict]:
        """
        Скачать файл из S3.
        
        :param object_key: Ключ объекта в S3
        :param download_path: Путь для сохранения файла
        :yield: SSE сообщения от S3 сервиса
        """
        s3_service = self._get_s3_service()
        
        download_data = {
            "data": {
                "operation": "download",
                "object_key": object_key,
                "download_path": str(download_path)
            }
        }
        
        async for msg in s3_service.execute_stream(download_data):
            yield msg

    async def _call_ml_service_sse(self, download_url: str) -> AsyncIterator[dict]:
        """
        Вызвать удаленный ML сервис и читать SSE поток.
        
        :param download_url: URL файла для обработки
        :yield: SSE сообщения от удаленного сервиса
        """
        with log_duration("Вызов удаленного ML сервиса (SSE)"):
            timeout = httpx.Timeout(
                connect=self.connect_timeout,
                read=self.sse_timeout,
                write=30.0,
                pool=30.0
            )
            
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with aconnect_sse(
                        client, 
                        "POST", 
                        self.sse_remote_url,
                        json={"download_url": download_url}
                    ) as event_source:
                        async for sse_event in event_source.aiter_sse():
                            try:
                                # Парсим JSON из SSE data
                                import json
                                event_data = json.loads(sse_event.data)
                                
                                # Проверяем тип сообщения
                                status = event_data.get("status")
                                
                                if status == "error":
                                    # Ошибка от ML сервиса
                                    error_info = event_data.get("error", {})
                                    yield self.create_error_message(
                                        error_code=error_info.get("code", "ML_ERROR"),
                                        error_message=error_info.get("message", "Unknown ML error"),
                                        stage_failed=error_info.get("stage_failed", "ml_processing"),
                                        error_details=error_info.get("details"),
                                        recoverable=error_info.get("recoverable", True)
                                    )
                                    return
                                
                                elif status == "success":
                                    # Успешное завершение
                                    yield {
                                        "progress": 100,
                                        "stage": "ml_complete",
                                        "status": "success",
                                        "result": event_data.get("result", {})
                                    }
                                    return
                                
                                else:
                                    # Прогресс сообщение
                                    yield {
                                        "progress": event_data.get("progress", 0),
                                        "stage": event_data.get("stage", "ml_processing"),
                                        "status": "processing",
                                        "details": event_data.get("details")
                                    }
                                    
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE event: {sse_event.data}, error: {e}")
                                continue
                                
            except httpx.TimeoutException as e:
                logger.error(f"Timeout при вызове ML сервиса: {e}")
                yield self.create_error_message(
                    error_code="TIMEOUT_ERROR",
                    error_message=f"Таймаут при обращении к ML сервису: {e}",
                    stage_failed="ml_processing",
                    recoverable=True
                )
                
            except httpx.RequestError as e:
                logger.error(f"Ошибка при вызове ML сервиса: {e}")
                yield self.create_error_message(
                    error_code="CONNECTION_ERROR",
                    error_message=f"Ошибка соединения с ML сервисом: {e}",
                    stage_failed="ml_processing",
                    recoverable=True
                )
                
            except Exception as e:
                logger.exception(f"Неожиданная ошибка при вызове ML сервиса: {e}")
                yield self.create_error_message(
                    error_code="INTERNAL_SERVICE_ERROR",
                    error_message=str(e),
                    stage_failed="ml_processing",
                    recoverable=False
                )
