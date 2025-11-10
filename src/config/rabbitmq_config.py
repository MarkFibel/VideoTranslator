"""
Конфигурация для подключения к RabbitMQ.
Загружает параметры из переменных окружения (.env файла).
"""

from pydantic_settings import BaseSettings


class RabbitMQSettings(BaseSettings):
    """
    Настройки подключения к RabbitMQ.
    Все параметры загружаются из переменных окружения.
    """
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASS: str
    RABBITMQ_VHOST: str = "/"
    
    # Имена очередей
    RABBITMQ_RPC_QUEUE: str = "rpc_requests_queue"
    RABBITMQ_REPLY_TO_QUEUE: str = "amq.rabbitmq.reply-to"
    
    # Настройки переподключения
    RABBITMQ_RECONNECT_DELAY: int = 5  # секунд
    RABBITMQ_MAX_RECONNECT_ATTEMPTS: int = 10  # 0 = бесконечно

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Игнорируем лишние поля из .env

    @property
    def url(self) -> str:
        """
        Генерирует URL для подключения к RabbitMQ в формате AMQP.
        
        :return: URL подключения (например, "amqp://guest:guest@localhost:5672/")
        """
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"


# Создаем единственный экземпляр настроек, который будет использоваться в компонентах RabbitMQ
rabbitmq_settings = RabbitMQSettings()
