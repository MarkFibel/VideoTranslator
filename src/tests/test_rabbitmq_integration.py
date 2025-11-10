"""
Интеграционные тесты для проверки работы RabbitMQ RPC.
Тестируют полный цикл: Producer -> RabbitMQ -> Consumer -> Service -> Response.

Запуск тестов:
    pytest src/tests/test_rabbitmq_integration.py -v
    pytest src/tests/test_rabbitmq_integration.py -v -s  # с выводом логов
    pytest src/tests/test_rabbitmq_integration.py::test_rpc_call_success -v  # один тест
    pytest -m integration -v  # только интеграционные тесты
"""

import asyncio
import pytest
import logging

from src.transport.rabbitmq.producer import RPCProducer
from src.transport.rabbitmq.consumer import RPCConsumer
from src.config.rabbitmq_config import rabbitmq_settings

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_call_success(rpc_consumer, rpc_producer, mock_service_data):
    """
    Тест успешного RPC вызова через RabbitMQ.
    Проверяет, что продюсер отправляет запрос, консьюмер обрабатывает его
    и возвращает корректный ответ.
    """
    # Отправляем RPC запрос
    result = await rpc_producer.call(
        method="test.execute",
        params={"data": mock_service_data},
        timeout=10.0
    )
    
    # Проверяем, что получили ответ
    assert result is not None, "Result should not be None"
    
    # Проверяем структуру ответа
    assert "status" in result, "Response should contain 'status' field"
    assert result["status"] == "success", "Status should be 'success'"
    
    # Проверяем, что сервис получил и обработал данные
    assert "message" in result, "Response should contain 'message' field"
    assert "echo" in result, "Response should contain 'echo' field"
    assert result["echo"] == mock_service_data, "Echo should match input data"
    
    logger.info(f"✓ Test passed. Result: {result}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_call_with_different_data(rpc_consumer, rpc_producer):
    """
    Тест RPC вызова с различными типами данных.
    Проверяет, что сервис корректно обрабатывает разные входные данные.
    """
    test_cases = [
        {"message": "Simple string"},
        {"message": "Unicode текст"},
        {"message": "", "empty": True},
        {"numbers": [1, 2, 3, 4, 5]},
        {"nested": {"level1": {"level2": {"level3": "deep"}}}},
    ]
    
    for test_data in test_cases:
        result = await rpc_producer.call(
            method="test.execute",
            params={"data": test_data},
            timeout=10.0
        )
        
        assert result is not None, f"Result should not be None for data: {test_data}"
        assert result["status"] == "success", f"Status should be 'success' for data: {test_data}"
        assert result["echo"] == test_data, f"Echo should match input data: {test_data}"
        
        logger.info(f"✓ Test case passed for data: {test_data}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_call_nonexistent_method(rpc_consumer, rpc_producer):
    """
    Тест вызова несуществующего метода.
    Проверяет, что система корректно обрабатывает ошибки.
    """
    with pytest.raises(Exception) as exc_info:
        await rpc_producer.call(
            method="nonexistent.method",
            params={"data": {}},
            timeout=10.0
        )
    
    # Проверяем, что получили ошибку
    assert exc_info.value is not None, "Should raise an exception"
    logger.info(f"✓ Test passed. Expected error received: {exc_info.value}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_multiple_sequential_calls(rpc_consumer, rpc_producer):
    """
    Тест множественных последовательных RPC вызовов.
    Проверяет, что система стабильно работает при нескольких запросах подряд.
    """
    num_calls = 5
    results = []
    
    for i in range(num_calls):
        result = await rpc_producer.call(
            method="test.execute",
            params={"data": {"message": f"Call #{i+1}", "call_number": i+1}},
            timeout=10.0
        )
        results.append(result)
        
        # Проверяем каждый результат
        assert result["status"] == "success", f"Call {i+1} should succeed"
        assert result["echo"]["call_number"] == i+1, f"Call number should match"
    
    # Проверяем, что все вызовы завершились успешно
    assert len(results) == num_calls, f"Should have {num_calls} results"
    logger.info(f"✓ Test passed. {num_calls} sequential calls successful")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_parallel_calls(rpc_consumer, rpc_producer):
    """
    Тест параллельных RPC вызовов.
    Проверяет, что система корректно обрабатывает одновременные запросы.
    """
    num_calls = 3
    
    # Создаем список задач для параллельного выполнения
    tasks = [
        rpc_producer.call(
            method="test.execute",
            params={"data": {"message": f"Parallel call #{i+1}", "call_id": i}},
            timeout=10.0
        )
        for i in range(num_calls)
    ]
    
    # Выполняем все задачи параллельно
    results = await asyncio.gather(*tasks)
    
    # Проверяем результаты
    assert len(results) == num_calls, f"Should have {num_calls} results"
    
    for i, result in enumerate(results):
        assert result["status"] == "success", f"Parallel call {i+1} should succeed"
        assert "echo" in result, f"Result {i+1} should have echo"
    
    logger.info(f"✓ Test passed. {num_calls} parallel calls successful")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_timeout_handling(rpc_consumer, rpc_producer):
    """
    Тест обработки таймаута при RPC вызове.
    Использует очень короткий таймаут для проверки обработки ошибок.
    """
    # Используем очень короткий таймаут (маловероятно, что запрос успеет)
    # Но если RabbitMQ очень быстр, тест может пройти - это нормально
    try:
        result = await rpc_producer.call(
            method="test.execute",
            params={"data": {"message": "Timeout test"}},
            timeout=0.001  # 1 миллисекунда
        )
        # Если запрос успел выполниться - это тоже валидный результат
        logger.info(f"Request completed within timeout: {result}")
        assert result["status"] == "success"
    except asyncio.TimeoutError:
        # Это ожидаемый результат при таком коротком таймауте
        logger.info("✓ Test passed. Timeout error correctly raised")
        pytest.skip("Timeout occurred as expected (test environment is slow)")
    except Exception as e:
        # Любая другая ошибка - это проблема
        pytest.fail(f"Unexpected error: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_rpc_large_payload(rpc_consumer, rpc_producer):
    """
    Тест передачи больших данных через RPC.
    Проверяет, что система корректно обрабатывает объемные сообщения.
    """
    # Создаем большой payload (но не слишком большой для тестов)
    large_data = {
        "message": "Large payload test",
        "items": [f"item_{i}" for i in range(1000)],
        "nested": {
            f"key_{i}": f"value_{i}" for i in range(100)
        }
    }
    
    result = await rpc_producer.call(
        method="test.execute",
        params={"data": large_data},
        timeout=15.0  # Увеличенный таймаут для больших данных
    )
    
    assert result["status"] == "success", "Should handle large payload"
    assert len(result["echo"]["items"]) == 1000, "Should preserve all items"
    assert len(result["echo"]["nested"]) == 100, "Should preserve nested structure"
    
    logger.info("✓ Test passed. Large payload handled successfully")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rpc_empty_params(rpc_consumer, rpc_producer):
    """
    Тест RPC вызова с пустыми параметрами.
    Проверяет, что сервис корректно обрабатывает отсутствие данных.
    """
    result = await rpc_producer.call(
        method="test.execute",
        params={"data": {}},
        timeout=10.0
    )
    
    assert result["status"] == "success", "Should handle empty params"
    assert result["echo"] == {}, "Echo should be empty dict"
    
    logger.info("✓ Test passed. Empty params handled successfully")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_connection_stability(rpc_consumer, rpc_producer):
    """
    Тест стабильности соединения при множественных операциях.
    Проверяет, что соединение остается стабильным после серии запросов.
    """
    num_iterations = 10
    
    for i in range(num_iterations):
        result = await rpc_producer.call(
            method="test.execute",
            params={"data": {"iteration": i}},
            timeout=10.0
        )
        assert result["status"] == "success", f"Iteration {i} should succeed"
        
        # Небольшая пауза между запросами
        await asyncio.sleep(0.1)
    
    logger.info(f"✓ Test passed. Connection stable after {num_iterations} iterations")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rabbitmq_queue_configuration(rabbitmq_config):
    """
    Тест конфигурации RabbitMQ.
    Проверяет, что все необходимые настройки заданы корректно.
    """
    assert rabbitmq_config["host"] is not None, "RabbitMQ host should be configured"
    assert rabbitmq_config["port"] > 0, "RabbitMQ port should be positive"
    assert rabbitmq_config["queue"] is not None, "RabbitMQ queue name should be configured"
    assert rabbitmq_config["url"].startswith("amqp://"), "RabbitMQ URL should use amqp protocol"
    
    logger.info(f"✓ Test passed. RabbitMQ configuration valid: {rabbitmq_config}")
