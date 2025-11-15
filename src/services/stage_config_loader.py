"""
Загрузчик конфигураций этапов обработки для SSE сервисов.
Автоматически обнаруживает и загружает YAML конфигурации этапов из директории sse_stages.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.services.service_stages import ServiceStage, ServiceStageDefinition
from src.utils.string_utils import to_snake_case

logger = logging.getLogger(__name__)


@dataclass 
class StageConfig:
    """Конфигурация этапа из YAML файла."""
    
    id: str
    progress: int
    supports_substeps: bool = False
    timeout_seconds: Optional[int] = None
    description: Optional[str] = None
    
    def to_service_stage(self) -> ServiceStage:
        """Конвертировать в ServiceStage."""
        return ServiceStage(
            id=self.id,
            progress=self.progress,
            supports_substeps=self.supports_substeps,
            timeout_seconds=self.timeout_seconds
        )


@dataclass
class ServiceStagesConfig:
    """Полная конфигурация этапов для сервиса."""
    
    service_name: str
    description: str
    stages: List[StageConfig]
    settings: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceStagesConfig':
        """Создать из словаря (загруженного из YAML)."""
        stages = []
        for stage_data in data.get("stages", []):
            stage = StageConfig(**stage_data)
            stages.append(stage)
        
        return cls(
            service_name=data.get("service_name", "unknown"),
            description=data.get("description", ""),
            stages=stages,
            settings=data.get("settings", {})
        )


class YAMLServiceStageDefinition(ServiceStageDefinition):
    """Реализация ServiceStageDefinition на основе YAML конфигурации."""
    
    def __init__(self, config: ServiceStagesConfig):
        """
        Инициализация с конфигурацией из YAML.
        
        :param config: Конфигурация этапов
        """
        self.config = config
        self._service_stages = [stage.to_service_stage() for stage in config.stages]
    
    def get_service_stages(self) -> List[ServiceStage]:
        """Получить этапы сервиса из YAML конфигурации."""
        return self._service_stages
    
    def get_settings(self) -> Dict[str, Any]:
        """Получить настройки из конфигурации."""
        return self.config.settings
    
    def should_auto_initialize(self) -> bool:
        """Нужно ли автоматически добавлять initializing этап."""
        return self.config.settings.get("auto_initialize", True)
    
    def should_auto_complete(self) -> bool:
        """Нужно ли автоматически добавлять complete этап."""
        return self.config.settings.get("auto_complete", True)
    
    def should_validate_sequence(self) -> bool:
        """Нужно ли проверять корректность последовательности."""
        return self.config.settings.get("validate_sequence", True)
    
    def allows_custom_stages(self) -> bool:
        """Разрешено ли сервису добавлять свои этапы."""
        return self.config.settings.get("allow_custom_stages", True)


class StageConfigLoader:
    """
    Загрузчик конфигураций этапов из YAML файлов.
    Работает по аналогии с ServiceLoader для автоматического обнаружения конфигураций.
    """
    
    def __init__(self, stages_dir: Optional[str] = None):
        """
        Инициализация загрузчика конфигураций этапов.
        
        :param stages_dir: Путь к директории с конфигурациями. 
                          По умолчанию используется src/config/services/sse_stages.
        """
        if stages_dir is None:
            # Определяем путь к директории stages относительно текущего файла
            current_file = Path(__file__)
            # current_file.parent = services/, .parent.parent = config/, .parent.parent.parent = src/
            src_root = current_file.parent.parent
            self.stages_dir = src_root / "config" / "services" / "sse_stages"
        else:
            self.stages_dir = Path(stages_dir)
        
        logger.info(f"StageConfigLoader initialized with directory: {self.stages_dir}")
        
        # Кеш загруженных конфигураций
        self._config_cache: Dict[str, ServiceStagesConfig] = {}
    
    def find_stage_config_files(self) -> List[Path]:
        """
        Находит все файлы *_stages.yaml в директории конфигураций.
        
        :return: Список путей к файлам с конфигурациями этапов.
        """
        config_files = []
        
        if not self.stages_dir.exists():
            logger.warning(f"Stages config directory not found: {self.stages_dir}")
            return config_files
        
        # Поиск файлов *_stages.yaml
        for file_path in self.stages_dir.glob("*_stages.yaml"):
            config_files.append(file_path)
            logger.debug(f"Found stage config file: {file_path}")
        
        logger.info(f"Found {len(config_files)} stage config files")
        return config_files
    
    def load_config_from_file(self, file_path: Path) -> Optional[ServiceStagesConfig]:
        """
        Загружает конфигурацию этапов из YAML файла.
        
        :param file_path: Путь к YAML файлу с конфигурацией.
        :return: Конфигурация этапов или None при ошибке.
        """
        try:
            logger.debug(f"Loading stage config from: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                logger.warning(f"Empty config file: {file_path}")
                return None
            
            config = ServiceStagesConfig.from_dict(data)
            
            # Валидация конфигурации
            if not config.stages:
                logger.warning(f"No stages defined in config: {file_path}")
                return None
            
            logger.debug(f"Loaded config for service: {config.service_name}")
            return config
        
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading config from {file_path}: {e}", exc_info=True)
        
        return None
    
    def extract_service_name_from_filename(self, file_path: Path) -> str:
        """
        Извлекает имя сервиса из имени файла.
        
        :param file_path: Путь к файлу конфигурации
        :return: Имя сервиса
        
        Примеры:
        - test_stages.yaml -> test
        - ml_stages.yaml -> ml  
        - file_service_stages.yaml -> file_service
        """
        filename = file_path.stem  # Без расширения
        if filename.endswith("_stages"):
            return filename[:-7]  # Убираем "_stages"
        return filename
    
    def load_all_configs(self) -> Dict[str, ServiceStagesConfig]:
        """
        Загружает все доступные конфигурации этапов.
        
        :return: Словарь {service_name: config}
        """
        configs = {}
        config_files = self.find_stage_config_files()
        
        for file_path in config_files:
            config = self.load_config_from_file(file_path)
            if config:
                # Используем имя сервиса из файла как ключ
                service_name = self.extract_service_name_from_filename(file_path)
                configs[service_name] = config
                
                logger.info(f"Registered stage config for service: {service_name}")
        
        # Кешируем загруженные конфигурации
        self._config_cache = configs
        logger.info(f"Total stage configs loaded: {len(configs)}")
        
        return configs
    
    def get_config_for_service(self, service_name: str) -> Optional[ServiceStagesConfig]:
        """
        Получает конфигурацию этапов для конкретного сервиса.
        
        :param service_name: Имя сервиса (обычно в snake_case)
        :return: Конфигурация этапов или None если не найдена
        """
        # Если кеш пуст, загружаем все конфигурации
        if not self._config_cache:
            self.load_all_configs()
        
        # Ищем точное совпадение
        if service_name in self._config_cache:
            return self._config_cache[service_name]
        
        # Ищем по преобразованному имени (на случай если передали CamelCase)
        snake_name = to_snake_case(service_name)
        if snake_name in self._config_cache:
            return self._config_cache[snake_name]
        
        # Ищем с удалением суффикса "service"
        if service_name.endswith("_service"):
            base_name = service_name[:-8]  # убираем "_service"
            if base_name in self._config_cache:
                return self._config_cache[base_name]
        
        logger.debug(f"No stage config found for service: {service_name}")
        return None
    
    def get_default_config(self) -> ServiceStagesConfig:
        """
        Получает дефолтную конфигурацию этапов.
        
        :return: Дефолтная конфигурация
        """
        default_config = self.get_config_for_service("default")
        if default_config:
            return default_config
        
        # Если дефолтный файл не найден, создаем минимальную конфигурацию
        logger.warning("Default stage config not found, creating minimal config")
        
        return ServiceStagesConfig(
            service_name="default",
            description="Minimal default configuration", 
            stages=[
                StageConfig(
                    id="processing",
                    progress=50,
                    supports_substeps=True,
                    timeout_seconds=300
                )
            ],
            settings={
                "auto_initialize": True,
                "auto_complete": True,
                "validate_sequence": True,
                "allow_custom_stages": True
            }
        )
    
    def create_stage_definition(self, service_name: str) -> YAMLServiceStageDefinition:
        """
        Создает ServiceStageDefinition для сервиса.
        
        :param service_name: Имя сервиса
        :return: Определение этапов на основе YAML конфигурации
        """
        config = self.get_config_for_service(service_name)
        if not config:
            logger.info(f"Using default stage config for service: {service_name}")
            config = self.get_default_config()
        
        return YAMLServiceStageDefinition(config)
    
    def reload_configs(self):
        """Перезагружает все конфигурации (очищает кеш и загружает заново)."""
        logger.info("Reloading stage configurations...")
        self._config_cache.clear()
        self.load_all_configs()


# Глобальный экземпляр загрузчика
_stage_loader: Optional[StageConfigLoader] = None


def get_stage_loader() -> StageConfigLoader:
    """Получить глобальный экземпляр загрузчика конфигураций."""
    global _stage_loader
    if _stage_loader is None:
        _stage_loader = StageConfigLoader()
    return _stage_loader


def get_stage_definition_for_service(service_name: str) -> YAMLServiceStageDefinition:
    """
    Вспомогательная функция для получения определения этапов сервиса.
    
    :param service_name: Имя сервиса
    :return: Определение этапов
    """
    loader = get_stage_loader()
    return loader.create_stage_definition(service_name)