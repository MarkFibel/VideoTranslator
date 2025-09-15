from dotenv import load_dotenv

from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "PP"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    CORS_ALLOWED_ORIGINS: str = "*"
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "var/log"
    
    # Настройки CSRF защиты
    CSRF_SECRET_KEY: str = "your-super-secret-csrf-key-change-in-production"
    CSRF_TOKEN_EXPIRES: int = 1800  # 30 минут в секундах
    
    class Config:
        env_file = ".env"


settings = Settings()