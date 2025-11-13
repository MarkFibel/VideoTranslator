from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All values can be overridden via .env file.
    """
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'  # Ignore extra fields (e.g., RabbitMQ config handled separately)
    
    # Основные настройки приложения
    PROJECT_NAME: str = "VideoTranslator"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "var/log"

    # Настройки загрузки файлов
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB в байтах
    
    # Временная директория
    TEMP_DIR: str = "var/temp"
    
    # Настройки сессий
    SESSIONS_SECRET_KEY: str = "change_me_in_production_please"
    SESSION_LIFETIME_HOURS: float = 12.0  # Время жизни сессии в часах (можно дробное для тестирования)
    SESSION_GC_THRESHOLD: int = 10  # Порог количества сессий для запуска GC (legacy, теперь используется periodic cleanup)
    SESSION_CLEANUP_INTERVAL_MINUTES: int = 5  # Интервал периодической очистки сессий в минутах
    
    # Настройки Yandex SmartCaptcha
    CAPTCHA_SITEKEY: str = ""  # Client-side ключ Yandex SmartCaptcha (получите на https://yandex.cloud/ru/services/smartcaptcha)
    CAPTCHA_SERVER_KEY: str = ""  # Server-side ключ для проверки капчи на сервере
    CAPTCHA_ENABLED: bool = False  # Включить/выключить проверку капчи (для разработки можно отключить)
    

settings = Settings()