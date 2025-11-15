import logging
import logging.config
from pathlib import Path
from typing import Dict, Any


def setup_logging(log_level: str = "INFO", log_dir: str = "var/log") -> None:
    """
    Настройка системы логирования для приложения.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Директория для сохранения файлов логов
    """
    # Создаем директорию для логов, если она не существует
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Конфигурация логирования
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file_info": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": str(log_path / "app.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": str(log_path / "error.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": ["console", "file_info", "file_error"]
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "file_error"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "sse": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "sse.connections": {
                "level": "DEBUG",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "sse.streaming": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": False
            },
            "sse.errors": {
                "level": "ERROR",
                "handlers": ["console", "file_error"],
                "propagate": False
            }
        }
    }
    
    # Применяем конфигурацию
    logging.config.dictConfig(logging_config)
    
    # Логируем информацию о запуске системы логирования
    logger = logging.getLogger(__name__)
    logger.info(f"Logging system initialized. Log files will be saved to: {log_path.absolute()}")
    logger.info(f"Log level set to: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер с указанным именем.
    
    Args:
        name: Имя логгера
        
    Returns:
        logging.Logger: Настроенный логгер
    """
    return logging.getLogger(name)