"""
Базовые классы для определения этапов обработки в сервисах.

Позволяет каждому сервису определить свои специфичные этапы
с соответствующими процентами выполнения.

ВАЖНО: Этот файл содержит только базовые классы. Конкретные конфигурации
этапов загружаются из YAML файлов через stage_config_loader.py
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

from src.schemas.sse_schemas import SSEProcessingStages


@dataclass
class ServiceStage:
    """Описание этапа обработки сервиса."""
    
    id: str                    # Техническое имя (snake_case)
    progress: int             # Процент выполнения (0-100)
    supports_substeps: bool = False   # Поддерживает ли подэтапы
    timeout_seconds: Optional[int] = None  # Максимальное время выполнения
    
    def __post_init__(self):
        """Валидация при создании."""
        if not self.id.islower() or not all(c.isalnum() or c == '_' for c in self.id):
            raise ValueError(f"Stage ID должно быть в формате snake_case: {self.id}")
        
        if not (0 <= self.progress <= 100):
            raise ValueError(f"Progress должен быть от 0 до 100: {self.progress}")


class ServiceStageDefinition(ABC):
    """
    Абстрактный базовый класс для определения этапов сервиса.
    
    Каждый сервис должен наследоваться от этого класса и определить
    свои специфичные этапы обработки.
    
    ПРИМЕЧАНИЕ: В новой архитектуре конкретные реализации загружаются
    из YAML конфигураций через stage_config_loader.py
    """
    
    @abstractmethod
    def get_service_stages(self) -> List[ServiceStage]:
        """
        Получить список этапов обработки для данного сервиса.
        
        :return: Список этапов в порядке выполнения
        """
        pass
    
    def get_all_stages(self) -> List[ServiceStage]:
        """
        Получить все этапы включая базовые универсальные.
        
        :return: Полный список этапов
        """
        # Базовые этапы
        base_stages = [
            ServiceStage(
                id=SSEProcessingStages.INITIALIZING,
                progress=0,
                supports_substeps=False
            )
        ]
        
        # Специфичные этапы сервиса
        service_stages = self.get_service_stages()
        
        # Финальные этапы
        final_stages = [
            ServiceStage(
                id=SSEProcessingStages.COMPLETE,
                progress=100,
                supports_substeps=False
            )
        ]
        
        return base_stages + service_stages + final_stages
    
    def get_stage_by_id(self, stage_id: str) -> Optional[ServiceStage]:
        """
        Найти этап по ID.
        
        :param stage_id: ID этапа
        :return: Этап или None если не найден
        """
        for stage in self.get_all_stages():
            if stage.id == stage_id:
                return stage
        return None
    
    def get_progress_for_stage(self, stage_id: str) -> int:
        """
        Получить процент выполнения для этапа.
        
        :param stage_id: ID этапа
        :return: Процент выполнения или -1 если этап не найден
        """
        stage = self.get_stage_by_id(stage_id)
        return stage.progress if stage else -1
    
    def validate_stage_sequence(self) -> bool:
        """
        Проверить корректность последовательности этапов.
        
        :return: True если последовательность корректна
        """
        stages = self.get_all_stages()
        
        # Проверяем, что проценты возрастают
        for i in range(1, len(stages) - 1):  # Исключаем complete этап
            if stages[i].progress <= stages[i-1].progress:
                return False
        
        # Проверяем уникальность ID
        stage_ids = [stage.id for stage in stages]
        return len(stage_ids) == len(set(stage_ids))
    
    def get_next_stage(self, current_stage_id: str) -> Optional[ServiceStage]:
        """
        Получить следующий этап после текущего.
        
        :param current_stage_id: ID текущего этапа
        :return: Следующий этап или None если текущий - последний
        """
        stages = self.get_all_stages()
        
        for i, stage in enumerate(stages):
            if stage.id == current_stage_id and i < len(stages) - 1:
                return stages[i + 1]
        
        return None
    
    def get_stage_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить информацию обо всех этапах в виде словаря.
        Полезно для логирования и отладки.
        
        :return: Словарь с информацией об этапах
        """
        stages = self.get_all_stages()
        return {
            stage.id: {
                "progress": stage.progress,
                "supports_substeps": stage.supports_substeps,
                "timeout_seconds": stage.timeout_seconds
            }
            for stage in stages
        }