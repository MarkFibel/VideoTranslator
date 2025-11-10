"""
Исключения для JSON-RPC обработки.
"""


class RPCException(Exception):
    """Базовое исключение для RPC операций."""
    pass


class ServiceNotFoundError(RPCException):
    """Исключение, возникающее когда сервис не найден."""
    pass


class ServiceLoadError(RPCException):
    """Исключение, возникающее при ошибке загрузки сервиса."""
    pass


class ServiceExecutionError(RPCException):
    """Исключение, возникающее при ошибке выполнения метода сервиса."""
    pass


class ConfigurationError(RPCException):
    """Исключение, возникающее при ошибке конфигурации сервиса."""
    pass
