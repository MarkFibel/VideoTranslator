"""
Универсальный executor для выполнения сервисов с SSE streaming.

Работает с любым сервисом, наследующим BaseService и реализующим execute_stream().
"""

import logging
from typing import AsyncIterator, Dict, Any
from src.services.base_service import BaseService
from src.utils.sse_formatter import SSEEventFormatter

logger = logging.getLogger(__name__)


class SSEServiceExecutor:
    """
    Универсальный executor для локального выполнения сервисов с SSE потоком.
    
    Использование:
        executor = SSEServiceExecutor()
        async for sse_event in executor.execute_service_stream(service_instance, params):
            yield sse_event
    """
    
    def __init__(self):
        self.formatter = SSEEventFormatter()
    
    async def execute_service_stream(
        self, 
        service: BaseService, 
        params: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Выполняет сервис локально и возвращает SSE поток событий.
        
        :param service: Экземпляр сервиса (наследник BaseService)
        :param params: Параметры для execute_stream(data)
        :yields: SSE события в формате строк
        """
        service_name = service.getName()
        logger.info(f"Starting SSE execution of service: {service_name}")
        
        try:
            # Вызываем execute_stream у сервиса
            async for message in service.execute_stream(params):
                # message - это dict от BaseService.create_progress_message() и т.д.
                
                # Преобразуем в SSE формат
                sse_event = self.formatter.format_event(message)
                
                yield sse_event
            
            logger.info(f"SSE execution completed: {service_name}")
            
        except Exception as e:
            logger.error(f"Error during SSE execution of {service_name}: {e}", exc_info=True)
            
            # Формируем ошибку через BaseService для единообразия
            error_message = service.create_error_message(
                error_code="SERVICE_EXECUTION_ERROR",
                error_message=f"Ошибка выполнения сервиса {service_name}",
                stage_failed="execution",
                error_details=str(e),
                recoverable=True
            )
            
            sse_error = self.formatter.format_event(error_message)
            yield sse_error
    
    async def execute_by_name(
        self, 
        service_name: str, 
        params: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Создает экземпляр сервиса по имени и выполняет его.
        
        :param service_name: Имя класса сервиса (например "TestService", "MLService")
        :param params: Параметры для execute_stream
        :yields: SSE события
        :raises ImportError: Если сервис не найден
        """
        # Динамический импорт сервиса
        try:
            # Пытаемся импортировать из src.services
            module_name = f"src.services.{service_name.lower()}"
            module = __import__(module_name, fromlist=[service_name])
            service_class = getattr(module, service_name)
            
            # Создаем экземпляр
            service_instance = service_class()
            
            # Выполняем через общий метод
            async for sse_event in self.execute_service_stream(service_instance, params):
                yield sse_event
                
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load service {service_name}: {e}")
            
            error_msg = {
                "progress": -1,
                "stage": "error",
                "status": "error",
                "error": {
                    "code": "SERVICE_NOT_FOUND",
                    "message": f"Сервис {service_name} не найден",
                    "details": str(e)
                }
            }
            
            yield self.formatter.format_event(error_msg)
