"""
Тестовый сервис для проверки работы JSON-RPC диспетчера.
"""

import logging
from src.services.base_service import BaseService

logger = logging.getLogger(__name__)


class TestService(BaseService):
    """
    Простой тестовый сервис для проверки RPC функционала.
    Конфигурация автоматически загружается из src/config/services/test_config.py
    """
    
    def execute(self, data: dict) -> dict:
        """
        Тестовый метод, который принимает данные и возвращает результат.
        
        :param data: Словарь с входными данными
        :return: Словарь с результатом выполнения
        """
        logger.info(f"TestService.execute called with data: {data}")
        
        # Получаем параметр message из входных данных
        message = data.get("message", "No message provided")
        
        # Формируем ответ
        result = {
            "status": "success",
            "message": f"Test service received: {message}",
            "echo": data,
            "service": self.getName()
        }
        
        logger.info(f"TestService.execute returning: {result}")
        
        return result
