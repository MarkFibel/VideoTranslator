from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar, Optional

load_dotenv()


class Settings(BaseSettings):
    # ===== Runtime flags =====
    RPC_ENABLED: bool = True

    # ===== ML Service Settings =====
    # URL для синхронного вызова ML сервиса
    REMOTE_URL: str = ''
    
    # URL для SSE (streaming) вызова ML сервиса
    SSE_REMOTE_URL: str = ''

    # Таймауты
    sse_timeout: int = 300  # seconds - таймаут для SSE соединения
    synchronous_timeout: int = 900  # seconds - таймаут для синхронного вызова
    
    # Таймаут на подключение к удаленному сервису
    connect_timeout: int = 30  # seconds


settings = Settings()
