import uvicorn
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic_settings import BaseSettings
from src.config.project_config import settings
from src.config.logging_config import setup_logging
from src.middleware import SecurityMiddleware, RequestLoggingMiddleware
from .routes import get_apps_router

# Инициализация системы логирования
setup_logging(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
logger = logging.getLogger(__name__)


# Настройки CSRF защиты
class CsrfSettings(BaseSettings):
    secret_key: str = settings.CSRF_SECRET_KEY
    cookie_samesite: str = "lax"


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()


def get_application() -> FastAPI:
    logger.info("Initializing FastAPI application")
    application = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version=settings.VERSION
    )
    
    # Добавляем обработчик CSRF ошибок
    @application.exception_handler(CsrfProtectError)
    async def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
        logger.warning(f"CSRF protection error: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message}
        )
    
    application.include_router(get_apps_router())

    # Настройка обслуживания статических файлов
    application.mount("/static", StaticFiles(directory="public"), name="static")
    logger.info("Static files mounted at /static")

    # Добавляем security middleware (должен быть первым)
    # application.add_middleware(SecurityMiddleware, max_request_size=settings.MAX_FILE_SIZE)
    # logger.info(f"Security middleware configured with max file size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB")
    
    # # Добавляем logging middleware
    # if settings.DEBUG:
    #     application.add_middleware(RequestLoggingMiddleware)
    #     logger.info("Request logging middleware configured")

    # application.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=settings.CORS_ALLOWED_ORIGINS.split(" "),
    #     allow_credentials=True,
    #     allow_methods=["*"],
    #     allow_headers=["*"],
    # )
    # logger.info("CORS middleware configured")
    # logger.info("FastAPI application initialized successfully")
    return application


app = get_application()


if __name__ == "__main__":
    logger.info("Starting application server")
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000)