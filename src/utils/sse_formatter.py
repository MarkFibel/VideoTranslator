"""
Универсальный форматтер для преобразования сообщений BaseService в SSE события.

Поддерживает автоматическое определение типа события по структуре сообщения.
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SSEEventFormatter:
    """
    Форматтер для преобразования dict-сообщений от BaseService в SSE события.
    
    Автоматически определяет тип события на основе структуры сообщения:
    - status="success" + progress=100 → event: complete
    - status="error" → event: error  
    - status="processing" → event: progress
    """
    
    @staticmethod
    def format_event(message: Dict[str, Any], event_type: str = None) -> str:
        """
        Преобразует dict-сообщение в SSE событие.
        
        :param message: Сообщение от BaseService (create_progress_message, etc.)
        :param event_type: Явно указанный тип события (если None - определяется автоматически)
        :return: Отформатированная SSE строка с двойным \n\n
        """
        if event_type is None:
            event_type = SSEEventFormatter._detect_event_type(message)
        
        # Формируем SSE событие
        sse_lines = []
        
        # Тип события
        if event_type:
            sse_lines.append(f"event: {event_type}")
        
        # Данные события
        data_json = json.dumps(message, ensure_ascii=False)
        sse_lines.append(f"data: {data_json}")
        
        # SSE требует двойной перевод строки в конце
        sse_event = "\n".join(sse_lines) + "\n\n"
        
        logger.debug(f"Formatted SSE event (type={event_type}): {sse_event[:200]}")
        
        return sse_event
    
    @staticmethod
    def _detect_event_type(message: Dict[str, Any]) -> str:
        """
        Автоматически определяет тип SSE события по структуре сообщения.
        
        :param message: Сообщение от BaseService
        :return: Тип события ("progress", "complete", "error")
        """
        status = message.get("status", "processing")
        progress = message.get("progress", 0)
        stage = message.get("stage", "")
        
        # Ошибка - всегда приоритет
        if status == "error" or "error" in message:
            return "error"
        
        # Успешное завершение
        if status == "success" and (progress == 100 or stage == "complete"):
            return "complete"
        
        # Промежуточный прогресс (по умолчанию)
        return "progress"
    
    @staticmethod
    def format_keepalive() -> str:
        """
        Создает SSE keepalive сообщение (комментарий).
        Используется для поддержания соединения активным.
        
        :return: SSE комментарий
        """
        return ": keepalive\n\n"
    
    @staticmethod
    def format_ping() -> str:
        """
        Создает SSE ping событие для поддержания соединения.
        
        :return: SSE ping событие
        """
        return "event: ping\ndata: {}\n\n"
    
    @staticmethod
    def format_custom_event(event_type: str, data: Dict[str, Any]) -> str:
        """
        Создает кастомное SSE событие с указанным типом.
        
        :param event_type: Тип события (любая строка)
        :param data: Данные события
        :return: Отформатированная SSE строка
        """
        data_json = json.dumps(data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {data_json}\n\n"
