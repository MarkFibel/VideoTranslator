"""
Реестр сервисов для SSE streaming.

Singleton реестр для прямого доступа к сервисам без RabbitMQ.
Используется для SSE endpoints, где нужна прямая потоковая передача.
"""

import logging
from typing import Dict, Optional, AsyncIterator
from src.services.base_service import BaseService
from src.transport.json_rpc.service_loader import ServiceLoader
from src.utils.sse_formatter import SSEEventFormatter

logger = logging.getLogger(__name__)


class SSEServiceRegistry:
    """
    Singleton реестр для прямого доступа к сервисам.
    
    Использует ленивую инициализацию - сервисы загружаются только при первом обращении.
    Предоставляет унифицированный интерфейс для SSE streaming.
    """
    
    _instance: Optional['SSEServiceRegistry'] = None
    _services_loaded: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Инициализируем базовые атрибуты, но не загружаем сервисы
        if not hasattr(self, 'services'):
            self.services: Dict[str, BaseService] = {}
            self.formatter = SSEEventFormatter()
            logger.info("SSEServiceRegistry created (services not loaded yet)")
    
    def _ensure_services_loaded(self):
        """
        Ленивая загрузка сервисов - вызывается при первом обращении.
        Это предотвращает загрузку сервисов при старте FastAPI приложения.
        """
        if not SSEServiceRegistry._services_loaded:
            logger.info("Loading services for SSEServiceRegistry (lazy initialization)...")
            self._discover_services()
            SSEServiceRegistry._services_loaded = True
    
    def _discover_services(self):
        """Обнаруживает и регистрирует все доступные сервисы."""
        loader = ServiceLoader()
        discovered_services = loader.discover_services()
        
        for service in discovered_services:
            method_name = loader.get_service_method_name(service)
            # Убираем ".execute" суффикс для более простого API
            service_name = method_name.replace('.execute', '')
            
            self.services[service_name] = service
            logger.info(f"Registered SSE service: {service_name}")
        
        logger.info(f"Total SSE services registered: {len(self.services)}")
    
    def get_service(self, service_name: str) -> Optional[BaseService]:
        """
        Получить сервис по имени.
        
        :param service_name: Имя сервиса (например "ml", "test")
        :return: Экземпляр сервиса или None
        """
        self._ensure_services_loaded()
        return self.services.get(service_name)
    
    def list_services(self) -> list[str]:
        """
        Получить список всех зарегистрированных сервисов.
        
        :return: Список имён сервисов
        """
        self._ensure_services_loaded()
        return list(self.services.keys())
    
    async def execute_service_stream(
        self, 
        service_name: str, 
        params: dict
    ) -> AsyncIterator[str]:
        """
        Выполнить сервис с SSE streaming.
        
        :param service_name: Имя сервиса (например "ml", "test")
        :param params: Параметры для execute_stream(data)
        :yields: SSE события в формате строк
        """
        service = self.get_service(service_name)
        
        if not service:
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "SERVICE_NOT_FOUND",
                    "message": f"Сервис '{service_name}' не найден",
                    "stage_failed": "initialization",
                    "recoverable": False
                }
            }
            yield self.formatter.format_event(error_msg)
            return
        
        logger.info(f"Starting SSE stream for service: {service_name}")
        
        try:
            # Вызываем execute_stream у сервиса
            async for message in service.execute_stream(params):
                # message - это dict от BaseService.create_progress_message() и т.д.
                sse_event = self.formatter.format_event(message)
                yield sse_event
            
            logger.info(f"SSE stream completed for service: {service_name}")
            
        except Exception as e:
            logger.error(f"Error during SSE stream for {service_name}: {e}", exc_info=True)
            
            error_message = service.create_error_message(
                error_code="SERVICE_EXECUTION_ERROR",
                error_message=f"Ошибка выполнения сервиса {service_name}",
                stage_failed="execution",
                error_details=str(e),
                recoverable=True
            )
            
            yield self.formatter.format_event(error_message)


# Глобальный экземпляр для удобства импорта
sse_registry = SSEServiceRegistry()
