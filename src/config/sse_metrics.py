"""
Метрики и мониторинг для Server-Sent Events (SSE) функциональности.

Содержит логгеры, метрики Prometheus и вспомогательные функции
для отслеживания состояния SSE соединений и производительности.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional, AsyncIterator, Any
import threading
from dataclasses import dataclass, field

# Глобальные счетчики для мониторинга SSE
class SSEMetrics:
    """Класс для отслеживания метрик SSE соединений."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._active_connections: int = 0
        self._total_connections: int = 0
        self._total_errors: int = 0
        self._connection_durations: list = []
        self._error_types: Dict[str, int] = {}
    
    def increment_connections(self) -> None:
        """Увеличить счетчик активных соединений."""
        with self._lock:
            self._active_connections += 1
            self._total_connections += 1
    
    def decrement_connections(self) -> None:
        """Уменьшить счетчик активных соединений."""
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)
    
    def record_connection_duration(self, duration: float) -> None:
        """Записать время жизни соединения."""
        with self._lock:
            self._connection_durations.append(duration)
            # Храним только последние 1000 записей
            if len(self._connection_durations) > 1000:
                self._connection_durations = self._connection_durations[-1000:]
    
    def record_error(self, error_type: str) -> None:
        """Записать ошибку по типу."""
        with self._lock:
            self._total_errors += 1
            self._error_types[error_type] = self._error_types.get(error_type, 0) + 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить текущие метрики."""
        with self._lock:
            avg_duration = 0.0
            if self._connection_durations:
                avg_duration = sum(self._connection_durations) / len(self._connection_durations)
            
            return {
                "active_connections": self._active_connections,
                "total_connections": self._total_connections,
                "total_errors": self._total_errors,
                "average_connection_duration": avg_duration,
                "error_types": dict(self._error_types)
            }
    
    def reset_metrics(self) -> None:
        """Сбросить все метрики."""
        with self._lock:
            self._active_connections = 0
            self._total_connections = 0
            self._total_errors = 0
            self._connection_durations.clear()
            self._error_types.clear()


# Глобальный экземпляр метрик
sse_metrics = SSEMetrics()


@dataclass
class SSEConnectionInfo:
    """Информация о SSE соединении."""
    
    connection_id: str
    start_time: float = field(default_factory=time.time)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    last_activity: float = field(default_factory=time.time)
    messages_sent: int = 0
    errors_count: int = 0
    
    def update_activity(self) -> None:
        """Обновить время последней активности."""
        self.last_activity = time.time()
    
    def increment_messages(self) -> None:
        """Увеличить счетчик отправленных сообщений."""
        self.messages_sent += 1
        self.update_activity()
    
    def increment_errors(self) -> None:
        """Увеличить счетчик ошибок."""
        self.errors_count += 1
        self.update_activity()
    
    def get_duration(self) -> float:
        """Получить время жизни соединения в секундах."""
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для логирования."""
        return {
            "connection_id": self.connection_id,
            "duration": self.get_duration(),
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "endpoint": self.endpoint,
            "messages_sent": self.messages_sent,
            "errors_count": self.errors_count,
            "last_activity": self.last_activity - self.start_time
        }


# Специализированные логгеры для SSE
def get_sse_logger() -> logging.Logger:
    """Получить основной логгер для SSE."""
    return logging.getLogger("sse")


def get_sse_connections_logger() -> logging.Logger:
    """Получить логгер для отслеживания соединений."""
    return logging.getLogger("sse.connections")


def get_sse_streaming_logger() -> logging.Logger:
    """Получить логгер для потоковой передачи данных."""
    return logging.getLogger("sse.streaming")


def get_sse_errors_logger() -> logging.Logger:
    """Получить логгер для ошибок SSE."""
    return logging.getLogger("sse.errors")


@asynccontextmanager
async def sse_connection_tracker(
    connection_id: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    endpoint: Optional[str] = None
) -> AsyncIterator[SSEConnectionInfo]:
    """
    Контекстный менеджер для отслеживания SSE соединения.
    
    :param connection_id: Уникальный идентификатор соединения
    :param client_ip: IP адрес клиента
    :param user_agent: User-Agent клиента
    :param endpoint: Endpoint SSE
    :yields: Информация о соединении
    """
    connections_logger = get_sse_connections_logger()
    
    # Создаем информацию о соединении
    connection_info = SSEConnectionInfo(
        connection_id=connection_id,
        client_ip=client_ip,
        user_agent=user_agent,
        endpoint=endpoint
    )
    
    # Увеличиваем счетчики
    sse_metrics.increment_connections()
    
    connections_logger.info(
        f"SSE connection opened: {connection_id}",
        extra={
            "connection_info": connection_info.to_dict(),
            "active_connections": sse_metrics.get_metrics()["active_connections"]
        }
    )
    
    try:
        yield connection_info
    
    except Exception as e:
        # Логируем ошибку соединения
        error_logger = get_sse_errors_logger()
        error_logger.error(
            f"SSE connection error: {connection_id}",
            extra={
                "connection_info": connection_info.to_dict(),
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        
        # Записываем ошибку в метрики
        sse_metrics.record_error(type(e).__name__)
        connection_info.increment_errors()
        
        raise
    
    finally:
        # Уменьшаем счетчики и записываем метрики
        duration = connection_info.get_duration()
        sse_metrics.decrement_connections()
        sse_metrics.record_connection_duration(duration)
        
        connections_logger.info(
            f"SSE connection closed: {connection_id}",
            extra={
                "connection_info": connection_info.to_dict(),
                "final_duration": duration,
                "active_connections": sse_metrics.get_metrics()["active_connections"]
            }
        )


def log_sse_message_sent(
    connection_info: SSEConnectionInfo,
    message_type: str,
    message_size: Optional[int] = None,
    processing_time: Optional[float] = None
) -> None:
    """
    Логировать отправку SSE сообщения.
    
    :param connection_info: Информация о соединении
    :param message_type: Тип сообщения (progress, complete, error, etc.)
    :param message_size: Размер сообщения в байтах
    :param processing_time: Время обработки сообщения
    """
    streaming_logger = get_sse_streaming_logger()
    connection_info.increment_messages()
    
    extra_data = {
        "connection_id": connection_info.connection_id,
        "message_type": message_type,
        "messages_sent": connection_info.messages_sent,
        "connection_duration": connection_info.get_duration()
    }
    
    if message_size is not None:
        extra_data["message_size"] = message_size
    
    if processing_time is not None:
        extra_data["processing_time"] = processing_time
    
    streaming_logger.debug(
        f"SSE message sent: {message_type} to {connection_info.connection_id}",
        extra=extra_data
    )


def log_sse_error(
    connection_id: str,
    error_type: str,
    error_message: str,
    stage: Optional[str] = None,
    recoverable: bool = True,
    **kwargs
) -> None:
    """
    Логировать ошибку SSE.
    
    :param connection_id: ID соединения
    :param error_type: Тип ошибки
    :param error_message: Сообщение об ошибке
    :param stage: Этап, на котором произошла ошибка
    :param recoverable: Можно ли восстановиться после ошибки
    :param kwargs: Дополнительные данные для логирования
    """
    error_logger = get_sse_errors_logger()
    sse_metrics.record_error(error_type)
    
    extra_data = {
        "connection_id": connection_id,
        "error_type": error_type,
        "stage": stage,
        "recoverable": recoverable,
        **kwargs
    }
    
    error_logger.error(
        f"SSE error in connection {connection_id}: {error_message}",
        extra=extra_data
    )


def get_sse_health_status() -> Dict[str, Any]:
    """
    Получить статус здоровья SSE подсистемы.
    
    :return: Словарь со статусом и метриками
    """
    metrics = sse_metrics.get_metrics()
    
    # Определяем статус здоровья
    health_status = "healthy"
    issues = []
    
    # Проверяем количество активных соединений
    if metrics["active_connections"] > 100:  # Настраиваемый лимит
        health_status = "warning"
        issues.append("High number of active connections")
    
    # Проверяем долю ошибок
    if metrics["total_connections"] > 0:
        error_rate = metrics["total_errors"] / metrics["total_connections"]
        if error_rate > 0.1:  # Более 10% ошибок
            health_status = "unhealthy"
            issues.append("High error rate")
    
    return {
        "status": health_status,
        "issues": issues,
        "metrics": metrics,
        "timestamp": time.time()
    }


def log_sse_health_status() -> None:
    """Логировать текущий статус здоровья SSE системы."""
    logger = get_sse_logger()
    health_status = get_sse_health_status()
    
    if health_status["status"] == "healthy":
        logger.info("SSE system health check: OK", extra=health_status)
    elif health_status["status"] == "warning":
        logger.warning("SSE system health check: WARNING", extra=health_status)
    else:
        logger.error("SSE system health check: UNHEALTHY", extra=health_status)


# Функция для сброса метрик (для тестирования)
def reset_sse_metrics() -> None:
    """Сбросить все SSE метрики."""
    sse_metrics.reset_metrics()
    logger = get_sse_logger()
    logger.info("SSE metrics reset")