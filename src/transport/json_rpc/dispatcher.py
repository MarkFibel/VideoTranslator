"""
JSON-RPC диспетчер для обработки RPC запросов.
Использует библиотеку jsonrpcserver для обработки JSON-RPC вызовов.
"""

import logging
from typing import Dict, Any
from jsonrpcserver import method, Success, Result, dispatch
from .service_loader import ServiceLoader
from src.services.base_service import BaseService
from src.exceptions.rpc_exceptions import ServiceExecutionError

logger = logging.getLogger(__name__)


class JSONRPCDispatcher:
    """
    Диспетчер для обработки JSON-RPC запросов.
    Автоматически обнаруживает и регистрирует сервисы при инициализации.
    """
    
    def __init__(self):
        """
        Инициализация диспетчера.
        Автоматически обнаруживает и регистрирует все доступные сервисы.
        """
        self.services: Dict[str, BaseService] = {}
        self._register_services()
        logger.info("JSONRPCDispatcher initialized")
    
    def _register_services(self):
        """
        Обнаруживает и регистрирует все доступные сервисы.
        """
        loader = ServiceLoader()
        discovered_services = loader.discover_services()
        
        for service in discovered_services:
            method_name = loader.get_service_method_name(service)
            self.services[method_name] = service
            
            # Регистрируем метод в jsonrpcserver
            self._register_method(method_name, service)
            
            logger.info(f"Registered RPC method: {method_name}")
        
        logger.info(f"Total RPC methods registered: {len(self.services)}")
    
    def _register_method(self, method_name: str, service: BaseService):
        """
        Регистрирует метод execute сервиса в jsonrpcserver.
        
        :param method_name: Имя RPC метода (например, "test.execute")
        :param service: Экземпляр сервиса
        """
        @method(name=method_name)
        def execute_wrapper(data: dict) -> Result:
            """
            Обертка для вызова метода execute сервиса.
            
            :param data: Данные для обработки сервисом
            :return: Success с результатом выполнения сервиса
            """
            try:
                logger.info(f"Executing RPC method: {method_name}")
                logger.debug(f"Request data: {data}")
                
                result = service.execute(data)
                
                logger.info(f"RPC method {method_name} executed successfully")
                logger.debug(f"Response data: {result}")
                
                # Возвращаем Success объект, как требует jsonrpcserver
                return Success(result)
            
            except Exception as e:
                logger.error(f"Error executing RPC method {method_name}: {e}", exc_info=True)
                raise ServiceExecutionError(f"Service execution failed: {str(e)}")
    
    def handle_request(self, request_body: str) -> str:
        """
        Обрабатывает входящий JSON-RPC запрос.
        
        :param request_body: Тело JSON-RPC запроса в виде строки
        :return: JSON-RPC ответ в виде строки
        """
        try:
            logger.info("Handling JSON-RPC request")
            logger.debug(f"Request body: {request_body}")
            
            # Используем dispatch из jsonrpcserver для обработки запроса
            response = dispatch(request_body)
            
            logger.info("JSON-RPC request handled successfully")
            logger.debug(f"Response: {response}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error handling JSON-RPC request: {e}", exc_info=True)
            # jsonrpcserver автоматически формирует error response
            raise
    
    def get_registered_methods(self) -> list[str]:
        """
        Возвращает список зарегистрированных RPC методов.
        
        :return: Список имен методов
        """
        return list(self.services.keys())
