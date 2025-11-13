"""
Конфигурация для сервиса Yandex Object Storage S3.
Загружает параметры из переменных окружения (.env файла).
"""

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional
import re

load_dotenv()


class Settings(BaseSettings):
    """
    Настройки для работы с Yandex Object Storage через S3-совместимый API (aioboto3).
    Все параметры загружаются из переменных окружения.
    
    Требуемые роли в Yandex Cloud:
    - storage.uploader - для загрузки файлов
    - storage.viewer - для чтения файлов
    - storage.editor - для удаления и управления объектами
    
    Как получить статические ключи доступа:
    https://yandex.cloud/ru/docs/iam/operations/sa/create-access-key
    """
    
    # Обязательные параметры для S3 API
    YA_S3_ACCESS_KEY_ID: str = ""  # Access Key ID для S3 API (из статического ключа)
    YA_S3_SECRET_ACCESS_KEY: str = ""  # Secret Access Key для S3 API (из статического ключа)
    YA_S3_BUCKET_NAME: str = "test-bucket"  # Имя бакета в Object Storage
    YA_S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"  # S3 endpoint URL
    YA_S3_REGION_NAME: str = "ru-central1"  # Регион Yandex Cloud
    YA_S3_REGION_NAME: str = "ru-central1"  # Регион Yandex Cloud
    
    # Настройки загрузки файлов
    YA_S3_MULTIPART_THRESHOLD_MB: int = 5  # Размер файла в МБ для переключения на multipart загрузку
    YA_S3_MULTIPART_CHUNK_SIZE_MB: int = 5  # Размер части для multipart загрузки в МБ
    YA_S3_MAX_PARALLEL_UPLOADS: int = 4  # Максимальное количество параллельных частей при multipart
    
    # Настройки таймаутов и повторных попыток
    YA_S3_OPERATION_TIMEOUT_SECONDS: float = 300.0  # Общий таймаут операции (5 минут)
    YA_S3_UPLOAD_TIMEOUT_SECONDS: float = 600.0  # Таймаут для загрузки файлов (10 минут)
    YA_S3_DOWNLOAD_TIMEOUT_SECONDS: float = 600.0  # Таймаут для скачивания файлов (10 минут)
    YA_S3_MAX_RETRIES: int = 3  # Максимальное количество повторных попыток
    YA_S3_RETRY_DELAY_SECONDS: float = 2.0  # Задержка между повторными попытками
    
    # Настройки URL и хранения
    YA_S3_PUBLIC_URL_TEMPLATE: str = "https://storage.yandexcloud.net/{bucket}/{key}"  # Шаблон публичного URL
    YA_S3_SIGNED_URL_EXPIRATION_HOURS: int = 24  # Время жизни подписанного URL в часах
    YA_S3_ENABLE_VERSIONING: bool = False  # Использовать версионирование объектов
    
    # Настройки RPC
    RPC_ENABLED: bool = True  # Включить регистрацию в JSON-RPC диспетчере
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'
    
    @field_validator('YA_S3_ENDPOINT_URL')
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        """
        Валидация формата endpoint URL.
        Ожидается формат: https://hostname или http://hostname
        """
        if not v:
            return v
        
        pattern = r'^https?://[a-zA-Z0-9.-]+$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid endpoint URL format: {v}. "
                f"Expected format: https://hostname (e.g., https://storage.yandexcloud.net)"
            )
        return v
    
    @field_validator('YA_S3_BUCKET_NAME')
    @classmethod
    def validate_bucket_name(cls, v: str) -> str:
        """
        Валидация имени бакета согласно правилам Yandex Object Storage.
        - Длина от 3 до 63 символов
        - Только строчные буквы, цифры, дефисы и точки
        - Не может начинаться или заканчиваться дефисом
        """
        if not v:
            return v
        
        if len(v) < 3 or len(v) > 63:
            raise ValueError(f"Bucket name length must be between 3 and 63 characters, got {len(v)}")
        
        pattern = r'^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid bucket name: {v}. "
                f"Must contain only lowercase letters, numbers, hyphens, and dots. "
                f"Cannot start or end with a hyphen."
            )
        return v
    
    @property
    def multipart_threshold_bytes(self) -> int:
        """Возвращает порог multipart загрузки в байтах."""
        return self.YA_S3_MULTIPART_THRESHOLD_MB * 1024 * 1024
    
    @property
    def multipart_chunk_size_bytes(self) -> int:
        """Возвращает размер части multipart загрузки в байтах."""
        return self.YA_S3_MULTIPART_CHUNK_SIZE_MB * 1024 * 1024
    
    def get_public_url(self, object_key: str) -> str:
        """
        Формирует публичный URL для объекта.
        
        :param object_key: Ключ объекта (имя файла/путь)
        :return: Публичный URL
        """
        return self.YA_S3_PUBLIC_URL_TEMPLATE.format(
            bucket=self.YA_S3_BUCKET_NAME,
            key=object_key
        )
    
    def validate_production_config(self) -> list[str]:
        """
        Проверяет критичные настройки для продакшена.
        
        :return: Список ошибок валидации (пустой если все ОК)
        """
        errors = []
        
        if not self.YA_S3_ACCESS_KEY_ID:
            errors.append("YA_S3_ACCESS_KEY_ID must be set in production")
        
        if not self.YA_S3_SECRET_ACCESS_KEY:
            errors.append("YA_S3_SECRET_ACCESS_KEY must be set in production")
        
        if not self.YA_S3_BUCKET_NAME or self.YA_S3_BUCKET_NAME == "test-bucket":
            errors.append("YA_S3_BUCKET_NAME must be set to a real bucket name in production")
        
        return errors


# Создаем единственный экземпляр настроек
settings = Settings()
