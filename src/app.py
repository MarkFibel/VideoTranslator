import uvicorn
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.config.app_config import settings
from src.config.logging_config import setup_logging
from .routes import get_apps_router

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