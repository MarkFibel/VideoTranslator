"""
Pydantic схемы для Server-Sent Events (SSE) сообщений.

Стандартизированные форматы для прогресса, успешного завершения и ошибок
в системе потоковой передачи данных VideoTranslator.
"""

from typing import Optional, Literal, Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class SSEMessageDetails(BaseModel):
    """Дополнительная информация о прогрессе обработки."""
    
    current_step: Optional[int] = Field(None, description="Текущий подэтап")
    total_steps: Optional[int] = Field(None, description="Общее количество подэтапов")
    eta_seconds: Optional[int] = Field(None, description="Примерное время до завершения в секундах")
    
    @field_validator('current_step', 'total_steps', 'eta_seconds')
    @classmethod
    def validate_positive_integers(cls, v: Optional[int]) -> Optional[int]:
        """Проверка, что числа положительные."""
        if v is not None and v < 0:
            raise ValueError("Значения должны быть положительными")
        return v


class SSEErrorInfo(BaseModel):
    """Информация об ошибке в SSE сообщении."""
    
    code: str = Field(..., description="Код ошибки в UPPERCASE_SNAKE_CASE")
    message: str = Field(..., description="Краткое описание ошибки")
    stage_failed: str = Field(..., description="На каком этапе произошла ошибка")
    details: Optional[str] = Field(None, description="Детальная техническая информация")
    recoverable: bool = Field(True, description="Можно ли повторить операцию")
    
    @field_validator('code')
    @classmethod
    def validate_error_code_format(cls, v: str) -> str:
        """Проверка формата кода ошибки."""
        if not v.isupper() or not all(c.isalpha() or c == '_' for c in v):
            raise ValueError("Код ошибки должен быть в формате UPPERCASE_SNAKE_CASE")
        return v


class SSEProgressMessage(BaseModel):
    """Схема для сообщений о прогрессе обработки."""
    
    progress: int = Field(..., ge=0, le=100, description="Процент выполнения (0-100)")
    stage: str = Field(..., description="Техническое имя этапа (snake_case)")
    status: Literal["processing"] = Field(default="processing", description="Статус обработки")
    timestamp: Optional[datetime] = Field(None, description="Временная метка события")
    details: Optional[SSEMessageDetails] = Field(None, description="Дополнительная информация")
    
    @field_validator('stage')
    @classmethod
    def validate_stage_format(cls, v: str) -> str:
        """Проверка формата stage (snake_case)."""
        if not v.islower() or not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("Stage должно быть в формате snake_case")
        return v


class SSESuccessMessage(BaseModel):
    """Схема для сообщений об успешном завершении."""
    
    progress: Literal[100] = Field(default=100, description="Процент выполнения (всегда 100)")
    stage: Literal["complete"] = Field(default="complete", description="Техническое имя этапа")
    status: Literal["success"] = Field(default="success", description="Статус обработки")
    timestamp: Optional[datetime] = Field(None, description="Временная метка события")
    result: Optional[Dict[str, Any]] = Field(None, description="Результат обработки")


class SSEErrorMessage(BaseModel):
    """Схема для сообщений об ошибках."""
    
    progress: Literal[-1] = Field(default=-1, description="Процент выполнения (всегда -1 для ошибок)")
    stage: Literal["error"] = Field(default="error", description="Техническое имя этапа")
    status: Literal["error"] = Field(default="error", description="Статус обработки")
    timestamp: Optional[datetime] = Field(None, description="Временная метка события")
    error: SSEErrorInfo = Field(..., description="Детали ошибки")


# Union тип для всех возможных SSE сообщений
SSEMessage = Union[SSEProgressMessage, SSESuccessMessage, SSEErrorMessage]


# Константы для стандартных кодов ошибок
class SSEErrorCodes:
    """Стандартизированные коды ошибок для различных сценариев."""
    
    # Ошибки валидации входных данных
    INVALID_INPUT = "INVALID_INPUT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    
    # Ошибки обработки видео
    FRAME_SPLIT_ERROR = "FRAME_SPLIT_ERROR"
    AUDIO_EXTRACTION_ERROR = "AUDIO_EXTRACTION_ERROR"
    VIDEO_ASSEMBLY_ERROR = "VIDEO_ASSEMBLY_ERROR"
    
    # Ошибки машинного обучения
    SPEECH_RECOGNITION_ERROR = "SPEECH_RECOGNITION_ERROR"
    TRANSLATION_ERROR = "TRANSLATION_ERROR"
    TTS_ERROR = "TTS_ERROR"
    FRAME_PROCESSING_ERROR = "FRAME_PROCESSING_ERROR"
    
    # Системные ошибки
    INTERNAL_SERVICE_ERROR = "INTERNAL_SERVICE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    DISK_SPACE_ERROR = "DISK_SPACE_ERROR"
    
    # Ошибки потоковой передачи
    STREAM_ERROR = "STREAM_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"


# Константы для базовых этапов обработки
class SSEProcessingStages:
    """Базовые этапы обработки, общие для всех сервисов."""
    
    # Универсальные этапы (используются всеми сервисами)
    INITIALIZING = "initializing"  # Начало любой задачи
    COMPLETE = "complete"          # Успешное завершение
    ERROR = "error"               # Ошибка обработки
    
    # Базовые проценты для универсальных этапов
    BASE_PROGRESS = {
        INITIALIZING: 0,
        COMPLETE: 100,
        ERROR: -1
    }
    
    @classmethod
    def get_progress_for_stage(cls, stage: str) -> int:
        """
        Получить прогресс для базового этапа.
        Для кастомных этапов сервисы должны определять свой прогресс.
        
        :param stage: Название этапа
        :return: Процент выполнения или -1 если этап не найден
        """
        return cls.BASE_PROGRESS.get(stage, -1)