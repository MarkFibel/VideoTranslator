"""
RabbitMQ консьюмер для обработки RPC запросов.
Слушает очередь, обрабатывает JSON-RPC запросы через диспетчер и отправляет ответы.
"""

import asyncio
import logging
from typing import Optional
import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage

from .connection import ConnectionManager
from src.config.rabbitmq_config import rabbitmq_settings
from src.transport.json_rpc.dispatcher import JSONRPCDispatcher

logger = logging.getLogger(__name__)


class RPCConsumer:
    """
    Консьюмер для обработки RPC запросов из RabbitMQ.
    
    Получает сообщения из очереди, передает их в JSONRPCDispatcher
    для обработки и отправляет ответы обратно клиенту.
    """

    def __init__(self, connection_manager: ConnectionManager = ConnectionManager(rabbitmq_settings.url), dispatcher: JSONRPCDispatcher = JSONRPCDispatcher()):
        """
        Инициализация консьюмера.
        
        :param connection_manager: Менеджер соединений с RabbitMQ
        :param dispatcher: JSON-RPC диспетчер для обработки запросов
        """
        self.connection_manager = connection_manager
        self.dispatcher = dispatcher
        logger.info("RPCConsumer initialized")
    
    async def start_consuming(self):
        """
        Запускает процесс прослушивания очереди и обработки сообщений.
        Блокирует выполнение до остановки консьюмера.
        """
        try:
            # Подключаемся к RabbitMQ
            channel = await self.connection_manager.get_channel()
            
            # Объявляем основную очередь для RPC запросов
            queue = await channel.declare_queue(
                rabbitmq_settings.RABBITMQ_RPC_QUEUE,
                durable=True  # Очередь переживет перезапуск RabbitMQ
            )
            
            logger.info(f"Started consuming from queue: {rabbitmq_settings.RABBITMQ_RPC_QUEUE}")
            
            # Начинаем слушать сообщения
            await queue.consume(self.on_message)
            
            # Блокируемся навсегда (пока не будет сигнала остановки)
            logger.info("Consumer is running. Press Ctrl+C to stop.")
            await asyncio.Event().wait()
        
        except Exception as e:
            logger.error(f"Error in consumer: {e}", exc_info=True)
            raise
    
    async def on_message(self, message: AbstractIncomingMessage):
        """
        Callback для обработки каждого входящего сообщения.
        
        :param message: Входящее сообщение из RabbitMQ
        """
        async with message.process():
            try:
                # Декодируем тело сообщения
                request_body = message.body.decode()
                logger.info(f"Received RPC request. Correlation ID: {message.correlation_id}")
                logger.debug(f"Request body: {request_body}")
                
                # Обрабатываем JSON-RPC запрос через диспетчер
                response_body = self.dispatcher.handle_request(request_body)
                
                logger.info(f"RPC request processed. Correlation ID: {message.correlation_id}")
                logger.debug(f"Response body: {response_body}")
                
                # Если клиент указал reply_to, отправляем ответ
                if message.reply_to:
                    await self._send_response(
                        message.reply_to,
                        response_body,
                        message.correlation_id
                    )
                else:
                    logger.warning("No reply_to address specified. Response will not be sent.")
            
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                
                # Пытаемся отправить ошибку клиенту, если указан reply_to
                if message.reply_to:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        },
                        "id": None
                    }
                    import json
                    await self._send_response(
                        message.reply_to,
                        json.dumps(error_response),
                        message.correlation_id
                    )
    
    async def _send_response(
        self,
        reply_to: str,
        response_body: str,
        correlation_id: Optional[str]
    ):
        """
        Отправляет ответ обратно клиенту.
        
        :param reply_to: Адрес очереди для ответа
        :param response_body: Тело ответа в формате JSON
        :param correlation_id: ID корреляции для связывания запроса и ответа
        """
        try:
            channel = await self.connection_manager.get_channel()
            
            # Формируем сообщение с ответом
            response_message = Message(
                body=response_body.encode(),
                correlation_id=correlation_id,
                content_type='application/json'
            )
            
            # Отправляем в указанную очередь (обычно amq.rabbitmq.reply-to)
            await channel.default_exchange.publish(
                response_message,
                routing_key=reply_to
            )
            
            logger.info(f"Response sent to {reply_to}. Correlation ID: {correlation_id}")
        
        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)


# Необходимо импортировать asyncio для Event
import asyncio
