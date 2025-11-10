"""
Тесты для проверки подключения и работы с RabbitMQ.
Тестируют ConnectionManager, Producer и Consumer на уровне транспорта.

Запуск тестов:
    pytest src/tests/test_rabbitmq_connection.py -v
    pytest -m connection -v  # только тесты подключения
"""

import pytest
import asyncio
import logging

from src.transport.rabbitmq.connection import ConnectionManager
from src.transport.rabbitmq.producer import RPCProducer
from src.config.rabbitmq_config import rabbitmq_settings

logger = logging.getLogger(__name__)


class TestConnectionManager:
    """
    Тесты для ConnectionManager.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_connection_manager_initialization(self, connection_manager):
        """
        Тест инициализации менеджера соединений.
        """
        assert connection_manager is not None, "ConnectionManager should be initialized"
        assert connection_manager.url == rabbitmq_settings.url, "URL should match settings"
        
        logger.info("✓ ConnectionManager initialization test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_get_channel(self, connection_manager):
        """
        Тест получения канала от менеджера соединений.
        """
        channel = await connection_manager.get_channel()
        
        assert channel is not None, "Channel should not be None"
        assert not channel.is_closed, "Channel should be open"
        
        logger.info("✓ Get channel test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_multiple_get_channel_calls(self, connection_manager):
        """
        Тест множественных вызовов get_channel.
        Проверяет, что возвращается один и тот же канал.
        """
        channel1 = await connection_manager.get_channel()
        channel2 = await connection_manager.get_channel()
        
        assert channel1 is channel2, "Should return the same channel instance"
        
        logger.info("✓ Multiple get_channel calls test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_connection_close(self):
        """
        Тест закрытия соединения.
        """
        manager = ConnectionManager(url=rabbitmq_settings.url)
        channel = await manager.get_channel()
        
        assert not channel.is_closed, "Channel should be open initially"
        
        await manager.close()
        
        # После закрытия канал должен быть закрыт
        assert channel.is_closed, "Channel should be closed after manager.close()"
        
        logger.info("✓ Connection close test passed")


class TestRPCProducer:
    """
    Тесты для RPCProducer.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_producer_initialization(self, connection_manager):
        """
        Тест инициализации продюсера.
        """
        producer = RPCProducer(connection_manager)
        
        assert producer is not None, "Producer should be initialized"
        assert producer.connection_manager is connection_manager, "Should store connection manager"
        
        logger.info("✓ Producer initialization test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_producer_connect(self, rpc_producer):
        """
        Тест подключения продюсера.
        Проверяет, что продюсер создает reply-to очередь.
        """
        assert rpc_producer._callback_queue is not None, "Callback queue should be created"
        assert rpc_producer._reply_to_queue_name is not None, "Reply-to queue name should be set"
        assert rpc_producer._consumer_tag is not None, "Consumer tag should be set"
        
        logger.info(f"✓ Producer connect test passed. Reply queue: {rpc_producer._reply_to_queue_name}")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_producer_close(self, connection_manager):
        """
        Тест закрытия продюсера.
        """
        producer = RPCProducer(connection_manager)
        await producer.connect()
        
        assert producer._callback_queue is not None, "Queue should exist before close"
        
        await producer.close()
        
        logger.info("✓ Producer close test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_producer_call_requires_connect(self, connection_manager):
        """
        Тест, что call() требует предварительного вызова connect().
        """
        producer = RPCProducer(connection_manager)
        # Не вызываем connect()
        
        with pytest.raises(Exception):
            await producer.call(
                method="test.execute",
                params={"data": {"message": "test"}},
                timeout=5.0
            )
        
        logger.info("✓ Producer call requires connect test passed")


class TestRabbitMQConfiguration:
    """
    Тесты конфигурации RabbitMQ.
    """
    
    @pytest.mark.unit
    def test_rabbitmq_settings_exist(self):
        """
        Тест наличия настроек RabbitMQ.
        """
        assert rabbitmq_settings is not None, "RabbitMQ settings should exist"
        assert rabbitmq_settings.RABBITMQ_HOST is not None, "Host should be configured"
        assert rabbitmq_settings.RABBITMQ_PORT > 0, "Port should be positive"
        assert rabbitmq_settings.RABBITMQ_RPC_QUEUE is not None, "Queue name should be configured"
        
        logger.info(f"✓ RabbitMQ settings test passed. Host: {rabbitmq_settings.RABBITMQ_HOST}")
    
    @pytest.mark.unit
    def test_rabbitmq_url_format(self):
        """
        Тест формата URL для подключения к RabbitMQ.
        """
        url = rabbitmq_settings.url
        
        assert url.startswith("amqp://"), "URL should use amqp protocol"
        assert rabbitmq_settings.RABBITMQ_HOST in url, "URL should contain host"
        
        logger.info(f"✓ RabbitMQ URL format test passed. URL: {url}")
    
    @pytest.mark.unit
    def test_rabbitmq_default_values(self):
        """
        Тест значений по умолчанию для RabbitMQ.
        """
        # Проверяем разумные значения по умолчанию
        assert rabbitmq_settings.RABBITMQ_PORT in [5672, 5671], "Port should be standard RabbitMQ port"
        assert len(rabbitmq_settings.RABBITMQ_RPC_QUEUE) > 0, "Queue name should not be empty"
        
        logger.info("✓ RabbitMQ default values test passed")


class TestRabbitMQReconnection:
    """
    Тесты переподключения к RabbitMQ при сбоях.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_connection_resilience(self, connection_manager):
        """
        Тест устойчивости соединения.
        Проверяет, что можно получить канал после инициализации.
        """
        # Первое подключение
        channel1 = await connection_manager.get_channel()
        assert not channel1.is_closed, "First channel should be open"
        
        # Повторное получение канала
        channel2 = await connection_manager.get_channel()
        assert not channel2.is_closed, "Second channel should be open"
        
        logger.info("✓ Connection resilience test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.connection
    async def test_producer_resilience_after_reconnect(self, connection_manager):
        """
        Тест устойчивости продюсера при переподключении.
        """
        # Создаем первого продюсера
        producer1 = RPCProducer(connection_manager)
        await producer1.connect()
        
        queue_name1 = producer1._reply_to_queue_name
        assert queue_name1 is not None, "First producer should have queue name"
        
        await producer1.close()
        
        # Создаем второго продюсера
        producer2 = RPCProducer(connection_manager)
        await producer2.connect()
        
        queue_name2 = producer2._reply_to_queue_name
        assert queue_name2 is not None, "Second producer should have queue name"
        
        # Очереди должны быть разными (новая эксклюзивная очередь)
        assert queue_name1 != queue_name2, "Queue names should be different"
        
        await producer2.close()
        
        logger.info("✓ Producer resilience test passed")
