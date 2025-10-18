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

    # Настройки загрузки файлов
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB в байтах
    
    class Config:
        env_file = ".env"


settings = Settings()