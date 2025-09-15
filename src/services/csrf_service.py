import asyncio
import logging
import threading
from typing import Dict, Set
from datetime import datetime, timedelta
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class CSRFTokenManager:
    """
    Менеджер CSRF токенов для защиты от DoS атак.
    Использует строгую блокировку токенов для предотвращения повторных запросов.
    """
    
    def __init__(self):
        # Множество активных токенов (в процессе обработки)
        self._active_tokens: Set[str] = set()
        
        # Словарь токенов с временными метками для очистки
        self._token_timestamps: Dict[str, datetime] = {}
        
        # Время жизни токена (по умолчанию 1 час)
        self._token_lifetime = timedelta(hours=1)
        
        # Флаг для отслеживания запуска фоновой задачи
        self._cleanup_task_started = False
        
        # Thread lock для синхронизации доступа к токенам
        self._lock = threading.RLock()
        
        logger.info("CSRF Token Manager initialized with strict locking")
    
    def _ensure_cleanup_task(self):
        """Запускает фоновую задачу очистки, если она еще не запущена"""
        if not self._cleanup_task_started:
            try:
                asyncio.create_task(self._cleanup_expired_tokens())
                self._cleanup_task_started = True
                logger.info("CSRF cleanup task started")
            except RuntimeError:
                # Event loop еще не запущен, задача будет запущена позже
                logger.debug("Event loop not running, cleanup task will start later")
    
    def is_token_available(self, token: str) -> bool:
        """
        Проверяет, доступен ли токен для использования.
        
        Args:
            token: CSRF токен для проверки
            
        Returns:
            True если токен свободен, False если занят или не существует
        """
        with self._lock:
            # Пытаемся запустить задачу очистки
            self._ensure_cleanup_task()
            
            # Проверяем, что токен не устарел
            if token in self._token_timestamps:
                if datetime.now() - self._token_timestamps[token] > self._token_lifetime:
                    self._cleanup_token_unsafe(token)
                    logger.debug(f"Token {token[:8]}... expired and cleaned up")
                    return False
            
            # Проверяем, что токен не активен
            is_available = token not in self._active_tokens
            
            logger.debug(f"Token {token[:8]}... availability check: {is_available}")
            return is_available
    
    def acquire_token(self, token: str) -> bool:
        """
        Захватывает токен для обработки с строгой блокировкой.
        
        Args:
            token: CSRF токен
            
        Returns:
            True если токен успешно захвачен, False если уже используется
        """
        with self._lock:
            if not self.is_token_available(token):
                logger.warning(f"Attempted to acquire already active token: {token[:8]}...")
                return False
            
            # Атомарно добавляем токен в активные
            self._active_tokens.add(token)
            self._token_timestamps[token] = datetime.now()
            
            logger.info(f"Token {token[:8]}... acquired for processing (locked)")
            return True
    
    def release_token(self, token: str) -> None:
        """
        Освобождает токен после завершения обработки.
        
        Args:
            token: CSRF токен для освобождения
        """
        with self._lock:
            if token in self._active_tokens:
                self._active_tokens.remove(token)
                logger.info(f"Token {token[:8]}... released from processing (unlocked)")
            else:
                logger.warning(f"Attempted to release non-active token: {token[:8]}...")
    
    def register_new_token(self, token: str) -> None:
        """
        Регистрирует новый токен в системе.
        
        Args:
            token: Новый CSRF токен
        """
        with self._lock:
            self._token_timestamps[token] = datetime.now()
            # Пытаемся запустить задачу очистки при регистрации токена
            self._ensure_cleanup_task()
            logger.debug(f"New token registered: {token[:8]}...")
    
    def _cleanup_token_unsafe(self, token: str) -> None:
        """
        Удаляет токен из всех внутренних структур данных.
        ВНИМАНИЕ: НЕ использует блокировку, должна вызываться внутри блока with self._lock
        
        Args:
            token: Токен для удаления
        """
        self._active_tokens.discard(token)
        self._token_timestamps.pop(token, None)
        logger.debug(f"Token {token[:8]}... cleaned up")
    
    def force_cleanup_token(self, token: str) -> None:
        """
        Принудительно удаляет токен из всех внутренних структур данных.
        
        Args:
            token: Токен для удаления
        """
        with self._lock:
            self._cleanup_token_unsafe(token)
            logger.info(f"Token {token[:8]}... force cleaned up")
    
    async def _cleanup_expired_tokens(self) -> None:
        """
        Фоновая задача для очистки устаревших токенов.
        Запускается каждые 5 минут.
        """
        while True:
            try:
                with self._lock:
                    current_time = datetime.now()
                    expired_tokens = [
                        token for token, timestamp in self._token_timestamps.items()
                        if current_time - timestamp > self._token_lifetime
                    ]
                    
                    for token in expired_tokens:
                        self._cleanup_token_unsafe(token)
                    
                    if expired_tokens:
                        logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
                
                # Ждем 5 минут до следующей очистки (чаще чем раньше)
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in token cleanup task: {e}", exc_info=True)
                await asyncio.sleep(60)  # Повторить через минуту при ошибке
    
    def get_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику по токенам.
        
        Returns:
            Словарь со статистикой
        """
        with self._lock:
            return {
                "active_tokens": len(self._active_tokens),
                "total_tokens": len(self._token_timestamps)
            }


# Глобальный экземпляр менеджера токенов
csrf_token_manager = CSRFTokenManager()


class CSRFProtectionError(HTTPException):
    """Исключение для ошибок CSRF защиты"""
    
    def __init__(self, detail: str = "CSRF token is currently being processed"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )


def validate_csrf_token_availability(token: str) -> None:
    """
    Проверяет доступность CSRF токена и захватывает его.
    Выбрасывает исключение если токен уже используется.
    
    Args:
        token: CSRF токен для проверки
        
    Raises:
        CSRFProtectionError: Если токен уже используется
    """
    if not csrf_token_manager.acquire_token(token):
        raise CSRFProtectionError(
            "This request is already being processed. Please wait for completion."
        )