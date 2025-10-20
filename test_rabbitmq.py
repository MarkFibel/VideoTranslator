"""
Тестовый скрипт для проверки работы RabbitMQ RPC.
Отправляет тестовые запросы через RPCProducer и проверяет ответы.

Использование:
    1. Запустите воркер: python -m src.worker
    2. В отдельном терминале запустите тест: python test_rabbitmq.py
"""

import asyncio
import logging
import sys

from src.transport.rabbitmq.producer import RPCProducer
from src.transport.rabbitmq.connection import ConnectionManager
from src.config.rabbitmq_config import rabbitmq_settings
from src.config.logging_config import setup_logging

# Настраиваем логирование
setup_logging()
logger = logging.getLogger(__name__)


async def test_rpc_call():
    """
    Тестирует RPC вызовы через RabbitMQ.
    """
    connection_manager = None
    producer = None
    
    try:
        logger.info("=" * 60)
        logger.info("RabbitMQ RPC Producer Test")
        logger.info("=" * 60)
        
        # Инициализация менеджера соединений
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_settings.RABBITMQ_HOST}:{rabbitmq_settings.RABBITMQ_PORT}")
        connection_manager = ConnectionManager(url=rabbitmq_settings.url)
        
        # Инициализация продюсера
        logger.info("Initializing RPC producer...")
        producer = RPCProducer(connection_manager)
        await producer.connect()
        
        logger.info("=" * 60)
        logger.info("Producer connected and ready to send requests")
        logger.info("=" * 60)
        
        # Тест 1: Вызов метода test.execute
        logger.info("\n" + "=" * 60)
        logger.info("Test 1: Calling 'test.execute' method")
        logger.info("=" * 60)
        
        try:
            result = await producer.call(
                method="test.execute",
                params={"data": {"message": "Hello from RabbitMQ!"}},
                timeout=10.0
            )
            logger.info(f"✓ Test 1 PASSED")
            logger.info(f"  Result: {result}")
        
        except Exception as e:
            logger.error(f"✗ Test 1 FAILED: {e}")
        
        # Тест 2: Вызов несуществующего метода
        logger.info("\n" + "=" * 60)
        logger.info("Test 2: Calling non-existent method (expecting error)")
        logger.info("=" * 60)
        
        try:
            result = await producer.call(
                method="nonexistent.method",
                params={},
                timeout=10.0
            )
            logger.error(f"✗ Test 2 FAILED: Expected error but got result: {result}")
        
        except Exception as e:
            logger.info(f"✓ Test 2 PASSED: Got expected error")
            logger.info(f"  Error: {e}")
        
        # Тест 3: Множественные последовательные вызовы
        logger.info("\n" + "=" * 60)
        logger.info("Test 3: Multiple sequential calls")
        logger.info("=" * 60)
        
        try:
            for i in range(3):
                result = await producer.call(
                    method="test.execute",
                    params={"data": {"message": f"Request #{i+1}"}},
                    timeout=10.0
                )
                logger.info(f"  Call {i+1}/3: {result}")
            
            logger.info(f"✓ Test 3 PASSED: All sequential calls successful")
        
        except Exception as e:
            logger.error(f"✗ Test 3 FAILED: {e}")
        
        # Тест 4: Параллельные вызовы
        logger.info("\n" + "=" * 60)
        logger.info("Test 4: Parallel calls")
        logger.info("=" * 60)
        
        try:
            tasks = [
                producer.call(
                    method="test.execute",
                    params={"data": {"message": f"Parallel request #{i+1}"}},
                    timeout=10.0
                )
                for i in range(3)
            ]
            
            results = await asyncio.gather(*tasks)
            
            for i, result in enumerate(results):
                logger.info(f"  Parallel call {i+1}/3: {result}")
            
            logger.info(f"✓ Test 4 PASSED: All parallel calls successful")
        
        except Exception as e:
            logger.error(f"✗ Test 4 FAILED: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("All tests completed!")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Fatal error in test: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Закрываем соединения
        if producer:
            await producer.close()
        if connection_manager:
            await connection_manager.close()
        
        logger.info("Test finished. Connections closed.")


async def main():
    """
    Главная функция теста.
    """
    try:
        await test_rpc_call()
    
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user (Ctrl+C)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
