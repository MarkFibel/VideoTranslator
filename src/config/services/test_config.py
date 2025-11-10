"""
Конфигурация для тестового сервиса.
Автоматически создан системой BaseService.
"""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Настройки для TestService"""
    RPC_ENABLED: bool = True


settings = Settings()
