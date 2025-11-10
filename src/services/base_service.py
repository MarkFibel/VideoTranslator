

import importlib
import os
from src.utils.string_utils import to_snake_case

class BaseService:
    """Базовый класс для всех сервисов."""
    
    def __init__(self):
        pass
    
    def getName(self) -> str:
        """Возвращает имя сервиса, которое является именем класса."""
        return self.__class__.__name__

    def get_config(self) -> dict:
        """
        Возвращает конфигурацию сервиса, используя имя сервиса для динамического импорта.
        Если файл конфигурации не найден, он создается с настройками по умолчанию.
        'SomeTestService' -> 'some_test_config'
        """
        service_name = self.getName()
        
        if service_name.endswith('Service'):
            base_name = service_name[:-7]
        else:
            base_name = service_name

        snake_case_name = to_snake_case(base_name)
        config_module_name = f"{snake_case_name}_config"
        config_module_path = f"src.config.services.{config_module_name}"

        try:
            config_module = importlib.import_module(config_module_path)
        except ImportError:
            # Файл конфигурации не найден, создаем его
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            config_file_path = os.path.join(project_root, 'src', 'config', 'services', f"{config_module_name}.py")
            
            default_config_content = """from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    RPC_ENABLED: bool = False

settings = Settings()
"""
            try:
                with open(config_file_path, 'w') as f:
                    f.write(default_config_content)
                # Повторно пытаемся импортировать модуль
                config_module = importlib.import_module(config_module_path)
            except Exception as e:
                print(f"Error creating or importing config for {service_name}: {e}")
                return {"RPC_ENABLED": False} # Возвращаем дефолт, если что-то пошло не так

        try:
            settings = getattr(config_module, 'settings', None)
            if settings:
                return settings.model_dump()
            else:
                return {}
        except Exception as e:
            print(f"Error loading config for {service_name}: {e}")
            return {}

    def execute(self, data: dict) -> dict:
        """Метод, который должен быть реализован в каждом сервисе."""
        raise NotImplementedError("Метод execute должен быть реализован в подклассе.")
