"""
Кастомное хранилище сессий с поддержкой очистки файлов.
Расширяет MemoryStore из fastsession с добавлением callback-механизма
для уведомления об удалении сессий.
"""

import time
import logging
from typing import Callable, Optional
from fastsession import MemoryStore

logger = logging.getLogger(__name__)


class CustomSessionStore(MemoryStore):
    """
    Расширенный MemoryStore с поддержкой очистки файлов при удалении сессий.
    
    Добавляет callback-механизм, который вызывается перед удалением каждой сессии,
    позволяя выполнить дополнительные действия (например, удаление связанных файлов).
    """
    
    def __init__(
        self, 
        on_session_delete: Optional[Callable[[str, dict], None]] = None,
        session_lifetime_hours: float = 12.0,
        gc_threshold: int = 10
    ):
        """
        Инициализация CustomSessionStore.
        
        :param on_session_delete: Callback функция, вызываемая перед удалением сессии.
                                  Сигнатура: fn(session_id: str, session_data: dict) -> None
                                  - session_id: Уникальный идентификатор сессии
                                  - session_data: Данные сессии (словарь)
        :param session_lifetime_hours: Время жизни сессии в часах (по умолчанию 12)
        :param gc_threshold: Количество сессий, при котором запускается GC (по умолчанию 10)
        """
        super().__init__()
        self.on_session_delete = on_session_delete
        self.session_lifetime_hours = session_lifetime_hours
        self.gc_threshold = gc_threshold
        logger.info(
            f"CustomSessionStore initialized: "
            f"session_lifetime={session_lifetime_hours}h, gc_threshold={gc_threshold}"
        )
    
    def gc(self):
        """
        Переопределенный метод сборки мусора.
        Запускает очистку при меньшем количестве сессий (по умолчанию >= 10).
        """
        if len(self.raw_memory_store) >= self.gc_threshold:
            logger.debug(f"GC triggered: {len(self.raw_memory_store)} sessions in store")
            self.cleanup_old_sessions()
    
    def cleanup_old_sessions(self):
        """
        Переопределенный метод очистки с вызовом callback.
        
        Находит все сессии старше заданного времени и удаляет их.
        Перед удалением каждой сессии вызывается callback (если установлен),
        что позволяет выполнить дополнительную очистку ресурсов.
        """
        current_time = int(time.time())
        sessions_to_delete = []
        
        # Находим сессии старше заданного времени жизни
        session_lifetime_seconds = self.session_lifetime_hours * 3600
        for session_id, session_info in self.raw_memory_store.items():
            if current_time - session_info["created_at"] > session_lifetime_seconds:
                sessions_to_delete.append(session_id)
        
        if sessions_to_delete:
            logger.info(f"Cleaning up {len(sessions_to_delete)} old sessions")
        
        # Удаляем каждую сессию с вызовом callback
        for session_id in sessions_to_delete:
            session_data = self.raw_memory_store[session_id].get("store", {})
            
            # Вызываем callback ДО удаления (если установлен)
            if self.on_session_delete:
                try:
                    self.on_session_delete(session_id, session_data)
                except Exception as e:
                    logger.error(
                        f"Error in on_session_delete callback for session {session_id}: {e}",
                        exc_info=True
                    )
                    # Продолжаем удаление сессии даже если callback упал
            
            # Удаляем сессию из памяти
            del self.raw_memory_store[session_id]
            logger.debug(f"Session {session_id} deleted from store")
