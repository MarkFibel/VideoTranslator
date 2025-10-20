"""
Загрузчик сервисов для JSON-RPC диспетчера.
Автоматически обнаруживает и регистрирует сервисы из директории src/services.
"""

import os
import importlib
import inspect
import logging
from pathlib import Path
from typing import List, Type, Optional
from src.services.base_service import BaseService
from src.exceptions.rpc_exceptions import ServiceLoadError
from src.utils.string_utils import to_snake_case

logger = logging.getLogger(__name__)


class ServiceLoader:
    """
    Класс для автоматического обнаружения и загрузки сервисов.
    Рекурсивно сканирует директорию src/services/ для поиска классов,
    наследующих BaseService.
    """
    
    def __init__(self, services_dir: Optional[str] = None):
        """
        Инициализация загрузчика сервисов.
        
        :param services_dir: Путь к директории с сервисами. 
                           По умолчанию используется src/services.
        """
        if services_dir is None:
            # Определяем путь к директории services относительно текущего файла
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            self.services_dir = project_root / "services"
        else:
            self.services_dir = Path(services_dir)
        
        logger.info(f"ServiceLoader initialized with directory: {self.services_dir}")
    
    def find_service_files(self) -> List[Path]:
        """
        Рекурсивно находит все файлы *_service.py в директории сервисов.
        
        :return: Список путей к файлам с сервисами.
        """
        service_files = []
        
        if not self.services_dir.exists():
            logger.warning(f"Services directory not found: {self.services_dir}")
            return service_files
        
        # Рекурсивный поиск файлов *_service.py
        for file_path in self.services_dir.rglob("*_service.py"):
            # Игнорируем base_service.py
            if file_path.name != "base_service.py":
                service_files.append(file_path)
                logger.debug(f"Found service file: {file_path}")
        
        logger.info(f"Found {len(service_files)} service files")
        return service_files
    
    def load_service_classes(self, file_path: Path) -> List[Type[BaseService]]:
        """
        Загружает классы сервисов из указанного файла.
        
        :param file_path: Путь к Python файлу с сервисами.
        :return: Список классов, наследующих BaseService.
        """
        service_classes = []
        
        try:
            # Преобразуем путь к файлу в имя модуля
            # Например: c:/project/src/services/test_service.py -> src.services.test_service
            relative_path = file_path.relative_to(file_path.parents[2])  # Относительно корня проекта
            module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
            
            logger.debug(f"Attempting to import module: {module_name}")
            
            # Импортируем модуль
            module = importlib.import_module(module_name)
            
            # Ищем классы, наследующие BaseService
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Проверяем, что это подкласс BaseService, но не сам BaseService
                if issubclass(obj, BaseService) and obj is not BaseService:
                    service_classes.append(obj)
                    logger.debug(f"Found service class: {name}")
            
        except Exception as e:
            logger.error(f"Error loading service from {file_path}: {e}", exc_info=True)
            raise ServiceLoadError(f"Failed to load service from {file_path}: {e}")
        
        return service_classes
    
    def discover_services(self) -> List[BaseService]:
        """
        Обнаруживает и создает экземпляры всех доступных сервисов.
        
        :return: Список экземпляров сервисов с включенным RPC.
        """
        services = []
        service_files = self.find_service_files()
        
        for file_path in service_files:
            try:
                service_classes = self.load_service_classes(file_path)
                
                for service_class in service_classes:
                    try:
                        # Создаем экземпляр сервиса
                        service_instance = service_class()
                        service_name = service_instance.getName()
                        
                        logger.info(f"Loading service: {service_name}")
                        
                        # Получаем конфигурацию сервиса
                        config = service_instance.get_config()
                        
                        # Проверяем, включен ли RPC для этого сервиса
                        if config.get("RPC_ENABLED", False):
                            services.append(service_instance)
                            logger.info(f"Service {service_name} registered (RPC enabled)")
                        else:
                            logger.info(f"Service {service_name} skipped (RPC disabled)")
                    
                    except Exception as e:
                        logger.error(
                            f"Error initializing service {service_class.__name__}: {e}",
                            exc_info=True
                        )
            
            except ServiceLoadError as e:
                logger.error(f"Service load error: {e}")
                continue
        
        logger.info(f"Total services registered: {len(services)}")
        return services
    
    def get_service_method_name(self, service: BaseService) -> str:
        """
        Формирует имя RPC метода для сервиса.
        
        :param service: Экземпляр сервиса.
        :return: Имя метода в формате snake_case.execute
        """
        service_name = service.getName()
        
        # Убираем суффикс Service, если он есть
        if service_name.endswith('Service'):
            base_name = service_name[:-7]
        else:
            base_name = service_name
        
        # Преобразуем в snake_case
        snake_name = to_snake_case(base_name)
        
        # Формируем имя метода
        method_name = f"{snake_name}.execute"
        
        return method_name
