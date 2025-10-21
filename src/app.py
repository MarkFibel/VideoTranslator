import uvicorn
import logging
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastsession import FastSessionMiddleware

from src.config.app_config import settings
from src.config.logging_config import setup_logging
from src.routes import get_apps_router
from src.utils.custom_session_store import CustomSessionStore
from src.utils.files_utils import cleanup_session_file, cleanup_orphaned_files

# Инициализация системы логирования
setup_logging(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
logger = logging.getLogger(__name__)


def get_application() -> FastAPI:
    logger.info("Initializing FastAPI application")
    application = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version=settings.VERSION
    )
    
    # Создаем store и сохраняем ссылку для фоновой задачи
    session_store = CustomSessionStore(
        on_session_delete=cleanup_session_file,
        session_lifetime_hours=settings.SESSION_LIFETIME_HOURS,
        gc_threshold=settings.SESSION_GC_THRESHOLD
    )
    
    application.add_middleware(
        FastSessionMiddleware,
        secret_key=settings.SESSIONS_SECRET_KEY,  # Key for cookie signature
        store=session_store,  # Custom store with file cleanup
        http_only=True,  # True: Cookie cannot be accessed from client-side scripts such as JavaScript
        secure=False,  # True: Requires Https
        max_age=0,
        # When 0 is specified, cookie is deleted when browser closes, but session remains on server
        # Sessions are cleaned up after SESSION_LIFETIME_HOURS (default 12h) when GC threshold is reached
        session_cookie="sid",  # Name of the session cookie
        session_object="session"  # Attribute name of the Session manager under request.state
    )
    
    # Фоновая задача для периодической очистки сессий
    async def periodic_session_cleanup():
        """
        Периодически вызывает cleanup_old_sessions() независимо от запросов пользователей.
        Интервал настраивается через SESSION_CLEANUP_INTERVAL_MINUTES.
        """
        cleanup_interval = settings.SESSION_CLEANUP_INTERVAL_MINUTES * 60  # Минуты в секунды
        logger.info(f"Periodic session cleanup task started (interval: {cleanup_interval}s = {settings.SESSION_CLEANUP_INTERVAL_MINUTES}min)")
        
        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                logger.debug("Running periodic session cleanup...")
                session_store.cleanup_old_sessions()
            except Exception as e:
                logger.error(f"Error in periodic session cleanup: {e}", exc_info=True)
    
    # Событие запуска: очистка orphaned файлов и запуск фоновой задачи
    @application.on_event("startup")
    async def startup_event():
        logger.info("Running startup tasks...")
        cleanup_orphaned_files(settings.TEMP_DIR, max_age_hours=24)
        
        # Запускаем фоновую задачу очистки сессий
        asyncio.create_task(periodic_session_cleanup())
        logger.info("Background tasks started")
    
    application.include_router(get_apps_router())

    # Настройка обслуживания статических файлов
    application.mount("/static", StaticFiles(directory="public"), name="static")
    logger.info("Static files mounted at /static")
    
    logger.info("FastAPI application initialized successfully")
    
    return application


app = get_application()


if __name__ == "__main__":
    logger.info("Starting application server")
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000)