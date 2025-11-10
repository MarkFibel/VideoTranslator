"""
Точка входа для запуска RabbitMQ воркера.
Запускает консьюмер для обработки RPC запросов из очереди.

Использование:
    python -m src.worker
"""

import asyncio
import logging
import sys

from src.transport.rabbitmq.consumer import RPCConsumer
from src.transport.rabbitmq.connection import ConnectionManager
from src.transport.json_rpc.dispatcher import JSONRPCDispatcher
from src.config.rabbitmq_config import rabbitmq_settings
from src.config.logging_config import setup_logging

# Настраиваем логирование
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """
    Главная функция запуска воркера.
    Инициализирует все компоненты и запускает консьюмер.
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting RabbitMQ Worker")
        logger.info("=" * 60)
        
        # Инициализация менеджера соединений
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_settings.RABBITMQ_HOST}:{rabbitmq_settings.RABBITMQ_PORT}")
        connection_manager = ConnectionManager(url=rabbitmq_settings.url)
        
        # Инициализация диспетчера (автоматически загружает сервисы)
        logger.info("Initializing JSON-RPC dispatcher...")
        dispatcher = JSONRPCDispatcher()
        
        # Инициализация консьюмера
        logger.info("Initializing RPC consumer...")
        consumer = RPCConsumer(connection_manager, dispatcher)
        
        logger.info("=" * 60)
        logger.info("RabbitMQ Worker is ready!")
        logger.info("Waiting for RPC requests... Press Ctrl+C to stop.")
        logger.info("=" * 60)
        
        # Запускаем консьюмер (блокирует выполнение)
        await consumer.start_consuming()
    
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Received shutdown signal (Ctrl+C)")
        logger.info("Stopping RabbitMQ Worker...")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Fatal error in worker: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        logger.info("RabbitMQ Worker stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Обрабатываем Ctrl+C на уровне asyncio.run()
        pass
