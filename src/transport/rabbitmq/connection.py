"""
Менеджер соединений с RabbitMQ.
Управляет установкой соединения, созданием каналов и переподключением при обрыве связи.
"""

import asyncio
import logging
from typing import Optional
import aio_pika
from aio_pika.abc import AbstractConnection, AbstractChannel
from aio_pika.exceptions import AMQPConnectionError

from src.config.rabbitmq_config import rabbitmq_settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Менеджер для управления подключением к RabbitMQ.
    
    Обеспечивает:
    - Установку и поддержание соединения
    - Создание каналов
    - Автоматическое переподключение при обрыве связи
    """
    
    def __init__(self, url: str):
        """
        Инициализация менеджера соединений.
        
        :param url: URL для подключения к RabbitMQ (формат: amqp://user:pass@host:port/vhost)
        """
        self.url = url
        self._connection: Optional[AbstractConnection] = None
        self._reconnect_attempts = 0
        logger.info(f"ConnectionManager initialized with URL: {url}")
    
    async def connect(self) -> AbstractConnection:
        """
        Устанавливает соединение с RabbitMQ.
        
        :return: Объект подключения
        :raises AMQPConnectionError: Если не удалось установить соединение
        """
        if self._connection and not self._connection.is_closed:
            logger.debug("Connection already established")
            return self._connection
        
        try:
            logger.info("Connecting to RabbitMQ...")
            self._connection = await aio_pika.connect_robust(self.url)
            self._reconnect_attempts = 0
            logger.info("Successfully connected to RabbitMQ")
            return self._connection
        
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def get_connection(self) -> AbstractConnection:
        """
        Возвращает активное соединение с RabbitMQ.
        Если соединение отсутствует или закрыто, устанавливает новое.
        
        :return: Объект подключения
        """
        if not self._connection or self._connection.is_closed:
            await self.connect()
        
        assert self._connection is not None, "Connection should be established"
        return self._connection
    
    async def get_channel(self) -> AbstractChannel:
        """
        Создает и возвращает новый канал из активного соединения.
        
        :return: Новый канал RabbitMQ
        """
        connection = await self.get_connection()
        channel = await connection.channel()
        logger.debug("New channel created")
        return channel
    
    async def reconnect(self) -> AbstractConnection:
        """
        Попытка переподключения к RabbitMQ с задержкой и ограничением попыток.
        
        :return: Объект подключения
        :raises AMQPConnectionError: Если исчерпаны все попытки переподключения
        """
        while rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS == 0 or self._reconnect_attempts < rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS:
            self._reconnect_attempts += 1
            logger.warning(
                f"Reconnection attempt {self._reconnect_attempts}"
                f"{f'/{rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS}' if rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS > 0 else ''}"
            )
            
            try:
                await asyncio.sleep(rabbitmq_settings.RABBITMQ_RECONNECT_DELAY)
                return await self.connect()
            
            except AMQPConnectionError as e:
                logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
                
                if rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS > 0 and self._reconnect_attempts >= rabbitmq_settings.RABBITMQ_MAX_RECONNECT_ATTEMPTS:
                    logger.critical("Max reconnection attempts reached. Giving up.")
                    raise
        
        raise AMQPConnectionError("Failed to reconnect to RabbitMQ")
    
    async def close(self):
        """
        Закрывает соединение с RabbitMQ.
        """
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("Connection to RabbitMQ closed")
