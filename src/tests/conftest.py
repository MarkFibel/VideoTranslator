"""
Pytest конфигурация и общие фикстуры для тестов.
"""

import asyncio
import logging
import pytest
import pytest_asyncio
from typing import AsyncGenerator

from src.config.logging_config import setup_logging
from src.transport.rabbitmq.connection import ConnectionManager
from src.transport.rabbitmq.producer import RPCProducer
from src.transport.rabbitmq.consumer import RPCConsumer
from src.transport.json_rpc.dispatcher import JSONRPCDispatcher
from src.config.rabbitmq_config import rabbitmq_settings

# Настраиваем логирование для тестов
setup_logging()
logger = logging.getLogger(__name__)


# Настройка event loop для async тестов
@pytest.fixture(scope="session")
def event_loop():
    """
    Создает event loop для async тестов на уровне всей сессии.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def connection_manager() -> AsyncGenerator[ConnectionManager, None]:
    """
    Фикстура для создания менеджера подключений к RabbitMQ.
    Автоматически закрывает соединение после теста.
    """
    manager = ConnectionManager(url=rabbitmq_settings.url)
    logger.info("ConnectionManager created for test")
    
    yield manager
    
    # Закрываем соединение после теста
    await manager.close()
    logger.info("ConnectionManager closed after test")


@pytest_asyncio.fixture(scope="function")
async def rpc_producer(connection_manager: ConnectionManager) -> AsyncGenerator[RPCProducer, None]:
    """
    Фикстура для создания RPC продюсера.
    Автоматически подключается и отключается.
    """
    producer = RPCProducer(connection_manager)
    await producer.connect()
    logger.info("RPCProducer connected for test")
    
    yield producer
    
    # Закрываем producer после теста
    await producer.close()
    logger.info("RPCProducer closed after test")


@pytest_asyncio.fixture(scope="function")
async def json_rpc_dispatcher() -> JSONRPCDispatcher:
    """
    Фикстура для создания JSON-RPC диспетчера.
    Автоматически регистрирует все доступные сервисы.
    """
    dispatcher = JSONRPCDispatcher()
    logger.info(f"JSONRPCDispatcher created with {len(dispatcher.services)} services")
    return dispatcher


@pytest_asyncio.fixture(scope="function")
async def rpc_consumer(
    connection_manager: ConnectionManager,
    json_rpc_dispatcher: JSONRPCDispatcher
) -> AsyncGenerator[RPCConsumer, None]:
    """
    Фикстура для создания RPC консьюмера для тестов.
    Запускает консьюмер в фоновой задаче.
    """
    consumer = RPCConsumer(connection_manager, json_rpc_dispatcher)
    logger.info("RPCConsumer created for test")
    
    # Запускаем консьюмер в фоновой задаче
    consumer_task = asyncio.create_task(consumer.start_consuming())
    
    # Даем время на инициализацию
    await asyncio.sleep(0.5)
    
    yield consumer
    
    # Останавливаем консьюмер после теста
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    
    logger.info("RPCConsumer stopped after test")


@pytest.fixture(scope="function")
def mock_service_data() -> dict:
    """
    Фикстура с тестовыми данными для сервисов.
    """
    return {
        "message": "Test message from pytest",
        "value": 42,
        "items": ["item1", "item2", "item3"]
    }


@pytest.fixture(scope="session")
def rabbitmq_config() -> dict:
    """
    Фикстура с конфигурацией RabbitMQ для тестов.
    """
    return {
        "host": rabbitmq_settings.RABBITMQ_HOST,
        "port": rabbitmq_settings.RABBITMQ_PORT,
        "url": rabbitmq_settings.url,
        "queue": rabbitmq_settings.RABBITMQ_RPC_QUEUE
    }
