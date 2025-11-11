"""
Утилиты для форматирования Server-Sent Events (SSE) сообщений.

Функции для корректного форматирования SSE event-stream данных
в соответствии со спецификацией W3C EventSource API.
"""

import json
import asyncio
from typing import Dict, Any, Union, AsyncIterator, Optional, Literal
from datetime import datetime

from src.schemas.sse_schemas import SSEMessage, SSEProgressMessage, SSESuccessMessage, SSEErrorMessage


def format_sse_event(
    data: Union[Dict[str, Any], SSEMessage],
    event_type: Optional[str] = None,
    event_id: Optional[str] = None,
    retry: Optional[int] = None
) -> str:
    """
    Форматирует данные в соответствии со стандартом SSE (Server-Sent Events).
    
    :param data: Данные для отправки (словарь или Pydantic модель)
    :param event_type: Тип события (progress, complete, error, keep-alive)
    :param event_id: Уникальный идентификатор события
    :param retry: Время повторного подключения в миллисекундах
    :return: Отформатированная SSE строка
    """
    lines = []
    
    # Добавляем тип события
    if event_type:
        lines.append(f"event: {event_type}")
    
    # Добавляем ID события
    if event_id:
        lines.append(f"id: {event_id}")
    
    # Добавляем retry время
    if retry is not None:
        lines.append(f"retry: {retry}")
    
    # Конвертируем данные в JSON  
    try:
        if hasattr(data, 'model_dump') and callable(getattr(data, 'model_dump')):
            # Pydantic модель
            json_data = json.dumps(data.model_dump(), ensure_ascii=False, default=str)  # type: ignore
        else:
            # Обычный словарь
            json_data = json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, AttributeError):
        # Fallback на обычное преобразование
        json_data = json.dumps(data, ensure_ascii=False, default=str)
    
    # Добавляем данные (могут быть многострочными)
    for line in json_data.split('\n'):
        lines.append(f"data: {line}")
    
    # Добавляем пустую строку в конце (обязательно для SSE)
    # Важно: SSE сообщения разделяются двойным \n\n
    lines.append("")
    lines.append("")  # Вторая пустая строка для двойного \n\n
    
    return '\n'.join(lines)


def format_sse_progress(
    progress: int,
    stage: str,
    event_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Форматирует сообщение о прогрессе для SSE.
    
    :param progress: Процент выполнения (0-100)
    :param stage: Техническое имя этапа
    :param event_id: ID события
    :param details: Дополнительная информация
    :return: Отформатированная SSE строка
    """
    from src.schemas.sse_schemas import SSEMessageDetails
    
    # Конвертируем details в Pydantic модель если нужно
    details_obj = None
    if details:
        details_obj = SSEMessageDetails(**details)
    
    message = SSEProgressMessage(
        progress=progress,
        stage=stage,
        timestamp=datetime.now(),
        details=details_obj
    )
    
    return format_sse_event(
        data=message,
        event_type="progress",
        event_id=event_id
    )


def format_sse_success(
    result: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None
) -> str:
    """
    Форматирует сообщение об успешном завершении для SSE.
    
    :param result: Результат обработки
    :param event_id: ID события
    :return: Отформатированная SSE строка
    """
    message = SSESuccessMessage(
        timestamp=datetime.now(),
        result=result
    )
    
    return format_sse_event(
        data=message,
        event_type="complete",
        event_id=event_id
    )


def format_sse_error(
    error_code: str,
    error_message: str,
    stage_failed: str,
    error_details: Optional[str] = None,
    recoverable: bool = True,
    event_id: Optional[str] = None
) -> str:
    """
    Форматирует сообщение об ошибке для SSE.
    
    :param error_code: Код ошибки
    :param error_message: Описание ошибки
    :param stage_failed: Этап, на котором произошла ошибка
    :param error_details: Детали ошибки
    :param recoverable: Можно ли повторить операцию
    :param event_id: ID события
    :return: Отформатированная SSE строка
    """
    from src.schemas.sse_schemas import SSEErrorInfo
    
    error_info = SSEErrorInfo(
        code=error_code,
        message=error_message,
        stage_failed=stage_failed,
        details=error_details,
        recoverable=recoverable
    )
    
    message = SSEErrorMessage(
        timestamp=datetime.now(),
        error=error_info
    )
    
    return format_sse_event(
        data=message,
        event_type="error",
        event_id=event_id
    )


def format_sse_keep_alive(
    comment: str = "keep-alive",
    event_id: Optional[str] = None
) -> str:
    """
    Форматирует keep-alive сообщение для SSE.
    
    :param comment: Комментарий для keep-alive
    :param event_id: ID события
    :return: Отформатированная SSE строка
    """
    lines = []
    
    # Keep-alive событие
    lines.append("event: keep-alive")
    
    if event_id:
        lines.append(f"id: {event_id}")
    
    # Комментарий вместо data
    lines.append(f": {comment}")
    lines.append("")
    
    return '\n'.join(lines)


async def sse_event_generator(
    messages: AsyncIterator[Dict[str, Any]],
    auto_event_type: bool = True,
    event_id_prefix: Optional[str] = None,
    keep_alive_interval: float = 30.0
) -> AsyncIterator[str]:
    """
    Генератор SSE событий из потока сообщений.
    
    :param messages: Асинхронный итератор сообщений
    :param auto_event_type: Автоматически определять тип события по содержимому
    :param event_id_prefix: Префикс для ID событий
    :param keep_alive_interval: Интервал keep-alive в секундах
    :yields: Отформатированные SSE строки
    """
    event_counter = 0
    last_activity = asyncio.get_event_loop().time()
    
    async def send_keep_alive():
        nonlocal event_counter
        event_counter += 1
        event_id = f"{event_id_prefix}-ka-{event_counter}" if event_id_prefix else None
        return format_sse_keep_alive(event_id=event_id)
    
    try:
        async for message in messages:
            current_time = asyncio.get_event_loop().time()
            
            # Отправляем keep-alive если прошло много времени
            if current_time - last_activity > keep_alive_interval:
                yield await send_keep_alive()
                last_activity = current_time
            
            event_counter += 1
            event_id = f"{event_id_prefix}-{event_counter}" if event_id_prefix else str(event_counter)
            
            # Автоматическое определение типа события
            event_type = None
            if auto_event_type:
                status = message.get('status')
                if status == 'processing':
                    event_type = 'progress'
                elif status == 'success':
                    event_type = 'complete'
                elif status == 'error':
                    event_type = 'error'
            
            yield format_sse_event(
                data=message,
                event_type=event_type,
                event_id=event_id
            )
            
            last_activity = current_time
            
            # Небольшая пауза для контроля потока
            await asyncio.sleep(0.01)
    
    except Exception as e:
        # В случае ошибки генератора отправляем ошибку
        event_counter += 1
        event_id = f"{event_id_prefix}-error-{event_counter}" if event_id_prefix else f"error-{event_counter}"
        
        yield format_sse_error(
            error_code="GENERATOR_ERROR",
            error_message="Ошибка генератора событий",
            stage_failed="event_generation",
            error_details=str(e),
            event_id=event_id
        )


def get_sse_headers() -> Dict[str, str]:
    """
    Возвращает стандартные заголовки для SSE ответов.
    
    :return: Словарь с заголовками
    """
    return {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Отключает буферизацию nginx
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Cache-Control"
    }


def validate_sse_message(data: Dict[str, Any]) -> bool:
    """
    Проверяет, является ли сообщение валидным SSE сообщением.
    
    :param data: Данные для проверки
    :return: True если сообщение валидно
    """
    try:
        # Проверяем наличие обязательных полей
        required_fields = ['progress', 'stage', 'status']
        for field in required_fields:
            if field not in data:
                return False
        
        # Проверяем типы и значения
        progress = data['progress']
        if not isinstance(progress, int) or (progress < -1 or progress > 100):
            return False
        
        status = data['status']
        if status not in ['processing', 'success', 'error']:
            return False
        
        # Специфические проверки по статусу
        if status == 'success' and progress != 100:
            return False
        
        if status == 'error' and progress != -1:
            return False
        
        return True
    
    except (KeyError, TypeError, ValueError):
        return False


# Константы для типов событий
class SSEEventTypes:
    """Стандартные типы SSE событий."""
    
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"
    KEEP_ALIVE = "keep-alive"
    HEARTBEAT = "heartbeat"


# Утилита для создания простых SSE сообщений
def create_simple_sse_message(
    message_type: Literal["info", "warning", "error"],
    text: str,
    event_id: Optional[str] = None
) -> str:
    """
    Создает простое SSE сообщение для уведомлений.
    
    :param message_type: Тип сообщения
    :param text: Текст сообщения
    :param event_id: ID события
    :return: Отформатированная SSE строка
    """
    data = {
        "type": message_type,
        "message": text,
        "timestamp": datetime.now().isoformat()
    }
    
    return format_sse_event(
        data=data,
        event_type="notification",
        event_id=event_id
    )