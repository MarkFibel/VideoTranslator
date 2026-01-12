"""
Обертка сервиса перевода видео.
"""

import os
import logging
from typing import AsyncIterator
from src.services.base_service import BaseService
from src.config.services.ml_config import settings
from contextlib import contextmanager
from time import perf_counter
import requests

@contextmanager
def log_duration(message: str):
    logger.info(f"⌛{message}")
    start = perf_counter()
    yield
    end = perf_counter()
    logger.info(f"Время выполнения: {end - start:.4f} сек")

logger = logging.getLogger(__name__)


class MLService(BaseService):
    """
    Обертка сервиса для обработки видео с применением ML-пайплайна.

    Этот класс выполняет вызов удаленного сервера выполняющего обработку видео.
    """

    def __init__(self):
        """
        Инициализация ML-сервиса.
        """

        super().__init__(settings)
        
        self.remote_url = self.get_settings.remote_url
        self.sse_timeout = self.get_settings.sse_timeout
        self.sinchronous_timeout = self.get_settings.sinchronous_timeout
        
        if not self.remote_url:
            raise ValueError("MLService initialization error: `remote_url` is not set in settings.")


    def execute(self, data: dict) -> dict:
        """
        Основной метод для вызова пайплайна обработки видео.

        Args:
            data (dict): Входные данные с ключами:
                - "download_url" (str): Путь к исходному видео.
                - "name" (str): Имя видео (без расширения).

        Returns:
            dict: Результат выполнения с ключами:
                - "status" (str): Статус выполнения ("success" или "error").
                - "message" (str): Сообщение о результате.
                - "echo" (dict): Исходные данные.
                - "service" (str): Имя сервиса.
        """
        
        logger.info(f"MLService.execute called with data: {data}")

        download_url = data.get("download_url")

        if not download_url:
            logging.info("❌ Ссылка на видео не указана")
            return {"status": "error", "message": "`download_url` missing"}

        # Вызов удаленного ML сервиса
        resp = self.__proccess_video()

        if resp.status is False:
            return {"status": "error", "message": resp.error}

        result = {
            "status": "success",
            "message": "",
            "echo": data,
            "service": self.getName()
        }

        logger.info(f"MLService.execute returning: {result}")
        return result

    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Streaming версия execute() для SSE.
        """

        try:
            download_url = data.get("download_url")

            # Основной streaming-пайплайн
            async for msg in self.__async_proccess_video():
                yield msg

            # Успешное завершение
            yield self.create_success_message(
                result=msg
            )

        except Exception as e:
            logger.exception("❌ Ошибка в execute_stream")
            yield self.create_error_message(
                error_code="ML_PROCESSING_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown"
            )

    async def __async_proccess_video(self, file_url) -> AsyncIterator[dict]:
        """
        Внутренний асинхронный метод для вызова удаленного ML сервиса.
        """

        with log_duration("Вызов удаленного ML сервиса (асинхронно)"):
            try:
                response = requests.post(
                    url=self.remote_url,
                    timeout=self.sse_timeout,  # Таймаут из настроек
                    json={'download_url': file_url}
                )
                response.raise_for_status()
                yield response.json()
            except requests.RequestException as e:
                logger.error(f"Ошибка при вызове ML сервиса: {e}")
                yield {"status": False, "error": str(e)}

    def __proccess_video(self, file_url) -> dict:
        """
        Внутренний метод для вызова удаленного ML сервиса.
        """

        with log_duration("Вызов удаленного ML сервиса"):
            try:
                response = requests.post(
                    url=self.remote_url,
                    timeout=self.sinchronous_timeout,  # Таймаут из настроек
                    json={'download_url': file_url}
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.error(f"Ошибка при вызове ML сервиса: {e}")
                return {"status": False, "error": str(e)}
