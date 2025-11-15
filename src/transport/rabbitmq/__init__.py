"""
Модуль для работы с RabbitMQ.
Содержит компоненты для отправки и получения сообщений через RabbitMQ.
"""

from .connection import ConnectionManager
from .producer import RPCProducer
from .consumer import RPCConsumer

__all__ = [
    'ConnectionManager',
    'RPCProducer',
    'RPCConsumer',
]
