class BaseError(Exception):
    """Базовый класс для всех пользовательских ошибок."""

    def __init__(self, message: str = "Произошла ошибка") -> None:
        super().__init__(message)
        self.message = message

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"
    
