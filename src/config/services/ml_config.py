from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar

load_dotenv()


class Settings(BaseSettings):
    # ✅ правильная конфигурация для Pydantic v2
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== Runtime flags =====
    RPC_ENABLED: bool = True

    # ===== Paths =====
    TEMP_DIR: str = "var/temp"
    MODEL_CACHE_DIR: str = "var/model_cache"

    # ===== Translator =====
    TRANSLATOR_NAME: str = "glazzova/translation_en_ru"
    TRANSLATOR_TYPE: str = "marian"
    TRANSLATOR_DEVICE: str = "mps"

    # ===== Speech recognition =====
    RECOGNIZER_NAME: str = "medium"
    RECOGNIZER_DEVICE: str = "cpu"

    # ===== OCR =====
    OCR_DEVICE: str = "mps"


settings = Settings()
