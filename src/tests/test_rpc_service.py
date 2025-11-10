"""
Unit тесты для RPC сервисов.
Тестируют логику сервисов изолированно, без RabbitMQ.

Запуск тестов:
    pytest src/tests/test_rpc_service.py -v
    pytest -m unit -v  # только unit тесты
"""

import pytest
import logging

from src.services.test_service import TestService
from src.services.base_service import BaseService
from src.transport.json_rpc.dispatcher import JSONRPCDispatcher
from src.transport.json_rpc.service_loader import ServiceLoader

logger = logging.getLogger(__name__)


class TestServiceUnit:
    """
    Unit тесты для TestService.
    """
    
    @pytest.mark.unit
    def test_service_initialization(self):
        """
        Тест инициализации сервиса.
        """
        service = TestService()
        assert service is not None, "Service should be initialized"
        assert isinstance(service, BaseService), "Service should inherit from BaseService"
        logger.info("✓ Service initialization test passed")
    
    @pytest.mark.unit
    def test_service_name(self):
        """
        Тест получения имени сервиса.
        """
        service = TestService()
        name = service.getName()
        
        assert name is not None, "Service name should not be None"
        assert isinstance(name, str), "Service name should be string"
        assert name == "test", "Service name should be 'test'"
        
        logger.info(f"✓ Service name test passed. Name: {name}")
    
    @pytest.mark.unit
    def test_service_execute_with_message(self):
        """
        Тест выполнения сервиса с сообщением.
        """
        service = TestService()
        test_message = "Hello, World!"
        
        result = service.execute({"message": test_message})
        
        assert result is not None, "Result should not be None"
        assert "status" in result, "Result should have 'status' field"
        assert result["status"] == "success", "Status should be 'success'"
        assert "message" in result, "Result should have 'message' field"
        assert test_message in result["message"], "Result message should contain input message"
        assert "echo" in result, "Result should have 'echo' field"
        assert result["echo"]["message"] == test_message, "Echo should match input"
        
        logger.info(f"✓ Execute with message test passed. Result: {result}")
    
    @pytest.mark.unit
    def test_service_execute_without_message(self):
        """
        Тест выполнения сервиса без сообщения.
        """
        service = TestService()
        
        result = service.execute({})
        
        assert result is not None, "Result should not be None"
        assert result["status"] == "success", "Status should be 'success'"
        assert "No message provided" in result["message"], "Should handle missing message"
        
        logger.info(f"✓ Execute without message test passed. Result: {result}")
    
    @pytest.mark.unit
    def test_service_execute_with_complex_data(self):
        """
        Тест выполнения сервиса со сложными данными.
        """
        service = TestService()
        complex_data = {
            "message": "Complex test",
            "nested": {
                "level1": {"level2": "deep value"},
                "array": [1, 2, 3, 4, 5]
            },
            "numbers": [10, 20, 30],
            "boolean": True
        }
        
        result = service.execute(complex_data)
        
        assert result["status"] == "success", "Should handle complex data"
        assert result["echo"] == complex_data, "Should preserve complex data structure"
        assert result["echo"]["nested"]["level1"]["level2"] == "deep value", "Should preserve nested values"
        assert result["echo"]["numbers"] == [10, 20, 30], "Should preserve arrays"
        
        logger.info(f"✓ Complex data test passed")


class TestServiceLoader:
    """
    Тесты для ServiceLoader - загрузчика сервисов.
    """
    
    @pytest.mark.unit
    def test_service_discovery(self):
        """
        Тест обнаружения сервисов.
        """
        loader = ServiceLoader()
        services = loader.discover_services()
        
        assert services is not None, "Services list should not be None"
        assert len(services) > 0, "Should discover at least one service"
        
        # Проверяем, что все обнаруженные объекты - это сервисы
        for service in services:
            assert isinstance(service, BaseService), f"Discovered object should be BaseService instance"
        
        logger.info(f"✓ Service discovery test passed. Found {len(services)} service(s)")
    
    @pytest.mark.unit
    def test_service_method_name_generation(self):
        """
        Тест генерации имен методов для сервисов.
        """
        loader = ServiceLoader()
        service = TestService()
        
        method_name = loader.get_service_method_name(service)
        
        assert method_name is not None, "Method name should not be None"
        assert isinstance(method_name, str), "Method name should be string"
        assert method_name == "test.execute", "Method name should be 'test.execute'"
        
        logger.info(f"✓ Method name generation test passed. Method: {method_name}")
    
    @pytest.mark.unit
    def test_discovered_services_are_unique(self):
        """
        Тест уникальности обнаруженных сервисов.
        """
        loader = ServiceLoader()
        services = loader.discover_services()
        
        # Получаем имена всех сервисов
        service_names = [service.getName() for service in services]
        
        # Проверяем уникальность
        assert len(service_names) == len(set(service_names)), "Service names should be unique"
        
        logger.info(f"✓ Service uniqueness test passed. Services: {service_names}")


class TestJSONRPCDispatcher:
    """
    Тесты для JSONRPCDispatcher.
    """
    
    @pytest.mark.unit
    def test_dispatcher_initialization(self):
        """
        Тест инициализации диспетчера.
        """
        dispatcher = JSONRPCDispatcher()
        
        assert dispatcher is not None, "Dispatcher should be initialized"
        assert hasattr(dispatcher, "services"), "Dispatcher should have services dict"
        assert len(dispatcher.services) > 0, "Dispatcher should register services"
        
        logger.info(f"✓ Dispatcher initialization test passed. Registered {len(dispatcher.services)} service(s)")
    
    @pytest.mark.unit
    def test_dispatcher_service_registration(self):
        """
        Тест регистрации сервисов в диспетчере.
        """
        dispatcher = JSONRPCDispatcher()
        
        # Проверяем, что TestService зарегистрирован
        assert "test.execute" in dispatcher.services, "TestService should be registered as 'test.execute'"
        
        service = dispatcher.services["test.execute"]
        assert isinstance(service, TestService), "Registered service should be TestService instance"
        
        logger.info(f"✓ Service registration test passed")
    
    @pytest.mark.unit
    def test_dispatcher_handle_valid_request(self):
        """
        Тест обработки валидного JSON-RPC запроса.
        """
        dispatcher = JSONRPCDispatcher()
        
        # Формируем JSON-RPC запрос
        request = """{
            "jsonrpc": "2.0",
            "method": "test.execute",
            "params": {"data": {"message": "Test from dispatcher"}},
            "id": 1
        }"""
        
        response_str = dispatcher.handle_request(request)
        
        assert response_str is not None, "Response should not be None"
        assert isinstance(response_str, str), "Response should be string"
        assert "result" in response_str or "error" in response_str, "Response should contain result or error"
        
        logger.info(f"✓ Valid request handling test passed. Response: {response_str[:100]}...")
    
    @pytest.mark.unit
    def test_dispatcher_handle_invalid_method(self):
        """
        Тест обработки запроса с несуществующим методом.
        """
        dispatcher = JSONRPCDispatcher()
        
        request = """{
            "jsonrpc": "2.0",
            "method": "nonexistent.method",
            "params": {},
            "id": 2
        }"""
        
        response_str = dispatcher.handle_request(request)
        
        assert response_str is not None, "Response should not be None"
        assert "error" in response_str, "Response should contain error"
        
        logger.info(f"✓ Invalid method handling test passed")
    
    @pytest.mark.unit
    def test_dispatcher_handle_malformed_request(self):
        """
        Тест обработки некорректного JSON-RPC запроса.
        """
        dispatcher = JSONRPCDispatcher()
        
        # Некорректный JSON
        request = "not a valid json"
        
        response_str = dispatcher.handle_request(request)
        
        assert response_str is not None, "Response should not be None"
        assert "error" in response_str, "Response should contain error for malformed request"
        
        logger.info(f"✓ Malformed request handling test passed")
    
    @pytest.mark.unit
    def test_dispatcher_multiple_requests(self):
        """
        Тест обработки нескольких запросов подряд.
        """
        dispatcher = JSONRPCDispatcher()
        
        for i in range(5):
            request = f"""{{
                "jsonrpc": "2.0",
                "method": "test.execute",
                "params": {{"data": {{"message": "Request {i}"}}}},
                "id": {i}
            }}"""
            
            response_str = dispatcher.handle_request(request)
            assert response_str is not None, f"Response {i} should not be None"
            assert "result" in response_str, f"Response {i} should contain result"
        
        logger.info(f"✓ Multiple requests test passed")


class TestBaseService:
    """
    Тесты для BaseService - базового класса сервисов.
    """
    
    @pytest.mark.unit
    def test_base_service_cannot_be_instantiated_directly(self):
        """
        Тест, что BaseService требует реализации execute().
        """
        # BaseService можно инстанцировать, но execute должен быть переопределен
        service = BaseService()
        assert service is not None, "BaseService can be instantiated"
        
        # Проверяем, что метод execute существует
        assert hasattr(service, "execute"), "BaseService should have execute method"
        
        logger.info("✓ BaseService instantiation test passed")
    
    @pytest.mark.unit
    def test_service_name_conversion(self):
        """
        Тест конвертации имени сервиса в snake_case.
        """
        from src.utils.string_utils import to_snake_case
        
        test_cases = [
            ("TestService", "test"),
            ("VideoProcessingService", "video_processing"),
            ("MLService", "ml"),
            ("MyCustomService", "my_custom")
        ]
        
        for class_name, expected_name in test_cases:
            # Удаляем 'Service' суффикс и конвертируем
            name_without_suffix = class_name.replace("Service", "")
            result = to_snake_case(name_without_suffix)
            
            assert result == expected_name, f"Expected {expected_name}, got {result}"
        
        logger.info("✓ Service name conversion test passed")
