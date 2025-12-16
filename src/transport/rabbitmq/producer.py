"""
RabbitMQ продюсер для отправки RPC запросов.
Использует паттерн Direct Reply-to для эффективного получения ответов без временных очередей.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional
import json

from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from .connection import ConnectionManager
from src.config.rabbitmq_config import rabbitmq_settings

logger = logging.getLogger(__name__)


class RPCProducer:
    """
    Продюсер для отправки RPC запросов через RabbitMQ.
    
    Использует паттерн Direct Reply-to для получения ответов:
    - reply_to='amq.rabbitmq.reply-to'
    - correlation_id для связывания запросов и ответов
    """
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """
        Инициализация продюсера.
        
        :param connection_manager: Менеджер соединений с RabbitMQ (если None - создается новый)
        """
        self.connection_manager = connection_manager or ConnectionManager(rabbitmq_settings.url)
        self._futures: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._callback_queue: Optional[AbstractQueue] = None
        self._consumer_tag: Optional[str] = None
        self._channel = None
        self._reply_to_queue_name: Optional[str] = None
        logger.info("RPCProducer initialized")
    
    async def connect(self):
        """
        Инициализация продюсера и создание временной очереди для ответов.
        Должен быть вызван перед использованием метода call().
        """
        self._channel = await self.connection_manager.get_channel()
        
        # Создаем временную эксклюзивную очередь для получения ответов
        # Эта очередь будет автоматически удалена при закрытии соединения
        self._callback_queue = await self._channel.declare_queue(
            name='',  # Пустое имя - RabbitMQ сгенерирует уникальное имя
            exclusive=True,  # Только это соединение может использовать очередь
            auto_delete=True  # Очередь удалится при закрытии соединения
        )
        
        # Сохраняем имя созданной очереди для использования в reply_to
        self._reply_to_queue_name = self._callback_queue.name
        
        # Начинаем слушать ответы
        self._consumer_tag = await self._callback_queue.consume(
            self._on_response,
            no_ack=True
        )
        
        logger.info(f"RPCProducer connected. Reply queue: {self._reply_to_queue_name}")
    
    async def call(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        """
        Выполняет RPC вызов удаленного метода.
        
        :param method: Имя метода для вызова (например, "test.execute")
        :param params: Параметры метода
        :param timeout: Таймаут ожидания ответа в секундах
        :return: Результат выполнения метода
        :raises TimeoutError: Если ответ не получен в течение timeout
        :raises Exception: При ошибке выполнения метода
        """
        # Используем блокировку для предотвращения одновременных вызовов
        async with self._lock:
            # Генерируем уникальный correlation_id
            correlation_id = str(uuid.uuid4())
            
            # Создаем Future для ожидания ответа
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._futures[correlation_id] = future
            
            try:
                # Формируем JSON-RPC запрос
                request_body = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": correlation_id
                }
                
                logger.info(f"Sending RPC request. Method: {method}, ID: {correlation_id}")
                logger.debug(f"Request: {request_body}")
                
                # Отправляем сообщение в основную очередь
                await self._publish_request(request_body, correlation_id)
                
                # Ждем ответа с таймаутом
                try:
                    response = await asyncio.wait_for(future, timeout=timeout)
                    logger.info(f"Received RPC response. ID: {correlation_id}")
                    logger.debug(f"Response: {response}")
                    return response
                
                except asyncio.TimeoutError:
                    logger.error(f"RPC request timeout. Method: {method}, ID: {correlation_id}")
                    raise TimeoutError(f"RPC call timeout after {timeout} seconds")
            
            finally:
                # Очищаем Future из словаря
                self._futures.pop(correlation_id, None)
    
    async def _publish_request(self, request_body: dict, correlation_id: str):
        """
        Отправляет запрос в основную очередь RPC.
        
        :param request_body: Тело JSON-RPC запроса
        :param correlation_id: ID корреляции для связывания запроса и ответа
        """
        if not self._channel:
            raise RuntimeError("Producer not connected. Call connect() first.")
        
        # Формируем сообщение
        message = Message(
            body=json.dumps(request_body).encode(),
            correlation_id=correlation_id,
            reply_to=self._reply_to_queue_name,  # Используем имя нашей временной очереди
            content_type='application/json'
        )
        
        # Публикуем в основную очередь запросов
        await self._channel.default_exchange.publish(
            message,
            routing_key=rabbitmq_settings.RABBITMQ_RPC_QUEUE
        )
        
        logger.debug(f"Request published to {rabbitmq_settings.RABBITMQ_RPC_QUEUE}")
    
    async def _on_response(self, message: AbstractIncomingMessage):
        """
        Callback для обработки ответов из очереди reply-to.
        
        :param message: Входящее сообщение с ответом
        """
        try:
            correlation_id = message.correlation_id
            
            if not correlation_id:
                logger.warning("Received response without correlation_id")
                return
            
            # Находим соответствующий Future
            future = self._futures.get(correlation_id)
            
            if not future:
                logger.warning(f"No pending request for correlation_id: {correlation_id}")
                return
            
            # Парсим ответ
            response_body = json.loads(message.body.decode())
            
            # Проверяем на ошибку JSON-RPC
            if "error" in response_body:
                error = response_body["error"]
                logger.error(f"RPC error: {error}")
                future.set_exception(
                    Exception(f"RPC Error [{error['code']}]: {error['message']}")
                )
            else:
                # Устанавливаем результат в Future
                result = response_body.get("result")
                future.set_result(result)
        
        except Exception as e:
            logger.error(f"Error processing response: {e}", exc_info=True)
            # Если есть correlation_id, устанавливаем ошибку в Future
            if correlation_id and correlation_id in self._futures:
                self._futures[correlation_id].set_exception(e)
    
    async def close(self):
        """
        Закрывает продюсер и отписывается от очереди ответов.
        """
        if self._callback_queue and self._consumer_tag:
            await self._callback_queue.cancel(self._consumer_tag)
            logger.info("RPCProducer closed")
