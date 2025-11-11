

import importlib
import os
import time
from typing import AsyncIterator, Optional
from datetime import datetime, timezone
from src.utils.string_utils import to_snake_case
from src.services.service_stages import ServiceStageDefinition

class BaseService:
    """Базовый класс для всех сервисов."""
    
    def __init__(self):
        self._start_time: Optional[float] = None
        self._stage_definition: Optional[ServiceStageDefinition] = None
    
    def get_stage_definition(self) -> ServiceStageDefinition:
        """
        Получить определение этапов для данного сервиса.
        
        Автоматически загружает конфигурацию этапов из YAML файла
        на основе имени сервиса.
        
        :return: Определение этапов сервиса
        """
        if self._stage_definition is None:
            # Импортируем здесь чтобы избежать циклических импортов
            from src.services.stage_config_loader import get_stage_definition_for_service
            
            # Получаем имя сервиса и загружаем соответствующую конфигурацию
            service_name = self.getName()
            
            # Убираем суффикс "Service" и преобразуем в snake_case
            if service_name.endswith('Service'):
                base_name = service_name[:-7]
            else:
                base_name = service_name
            
            snake_case_name = to_snake_case(base_name)
            
            # Загружаем определение этапов из YAML
            self._stage_definition = get_stage_definition_for_service(snake_case_name)
        
        return self._stage_definition
    
    def set_stage_definition(self, stage_type: str):
        """
        Установить тип определения этапов для сервиса.
        
        :param stage_type: Тип определения этапов (имя YAML конфигурации)
        """
        from src.services.stage_config_loader import get_stage_definition_for_service
        self._stage_definition = get_stage_definition_for_service(stage_type)
    
    def get_progress_for_stage(self, stage_id: str) -> int:
        """
        Получить процент выполнения для этапа.
        
        :param stage_id: ID этапа
        :return: Процент выполнения
        """
        return self.get_stage_definition().get_progress_for_stage(stage_id)
    
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
    
    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Новый асинхронный метод для streaming обработки.
        Дочерние сервисы могут переопределить этот метод
        для отправки промежуточных результатов.
        
        Дефолтная реализация: вызывает execute и yield'ит результат для обратной совместимости.
        """
        result = self.execute(data)
        yield {"_final": True, **result}
    
    #region Методы отслеживания времени 
    def _start_tracking(self):
        """Начать отслеживание времени обработки."""
        self._start_time = time.time()
    
    def _get_elapsed_time(self) -> float:
        """Получить прошедшее время в секундах."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time
    
    def _calculate_eta(self, current_progress: int) -> Optional[int]:
        """
        Рассчитать примерное время до завершения (ETA) в секундах.
        
        :param current_progress: Текущий прогресс (0-100)
        :return: ETA в секундах или None если рассчитать невозможно
        """
        if self._start_time is None or current_progress <= 0:
            return None
        
        elapsed = self._get_elapsed_time()
        progress_ratio = current_progress / 100.0
        
        if progress_ratio > 0:
            total_estimated = elapsed / progress_ratio
            eta = total_estimated - elapsed
            return int(max(0, eta))
        
        return None
    #endregion
    
    #region Вспомогательные методы для создания стандартизированных ответов
    def create_progress_message(
        self,
        progress: int,
        stage: str,
        status: str = "processing",
        include_timestamp: bool = True,
        details: Optional[dict] = None
    ) -> dict:
        """
        Создать стандартизированное сообщение о прогрессе.
        
        :param progress: Процент выполнения (0-100)
        :param stage: Техническое имя этапа (snake_case)
        :param status: Статус обработки ("processing", "success", "error")
        :param include_timestamp: Включить временную метку
        :param details: Дополнительная информация (current_step, total_steps, eta_seconds)
        :return: Словарь с сообщением о прогрессе
        """
        message = {
            "progress": progress,
            "stage": stage,
            "status": status
        }
        
        if include_timestamp:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        if details:
            message["details"] = details
        
        return message
    
    def create_success_message(
        self,
        result: Optional[dict] = None,
        include_timestamp: bool = True
    ) -> dict:
        """
        Создать стандартизированное сообщение об успешном завершении.
        
        :param result: Результат обработки
        :param include_timestamp: Включить временную метку
        :return: Словарь с финальным сообщением
        """
        message = {
            "progress": 100,
            "stage": "complete",
            "status": "success"
        }
        
        if include_timestamp:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        if result:
            message["result"] = result
        
        return message
    
    def create_error_message(
        self,
        error_code: str,
        error_message: str,
        stage_failed: str,
        error_details: Optional[str] = None,
        recoverable: bool = True,
        include_timestamp: bool = True
    ) -> dict:
        """
        Создать стандартизированное сообщение об ошибке.
        
        :param error_code: Код ошибки (UPPERCASE_SNAKE_CASE)
        :param error_message: Краткое описание ошибки
        :param stage_failed: На каком этапе произошла ошибка
        :param error_details: Детальная техническая информация
        :param recoverable: Можно ли повторить операцию
        :param include_timestamp: Включить временную метку
        :return: Словарь с сообщением об ошибке
        """
        error_obj = {
            "code": error_code,
            "message": error_message,
            "stage_failed": stage_failed,
            "recoverable": recoverable
        }
        
        if error_details:
            error_obj["details"] = error_details
        
        message = {
            "progress": -1,
            "stage": "error",
            "status": "error",
            "error": error_obj
        }
        
        if include_timestamp:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        return message
    
    def create_progress_with_substeps(
        self,
        progress: int,
        stage: str,
        current_step: int,
        total_steps: int,
        include_eta: bool = False
    ) -> dict:
        """
        Создать сообщение о прогрессе с информацией о подэтапах.
        
        :param progress: Основной процент выполнения (0-100)
        :param stage: Техническое имя этапа
        :param current_step: Текущий подэтап
        :param total_steps: Общее количество подэтапов
        :param include_eta: Включить расчет ETA
        :return: Словарь с сообщением о прогрессе
        """
        details = {
            "current_step": current_step,
            "total_steps": total_steps
        }
        
        if include_eta:
            eta = self._calculate_eta(progress)
            if eta is not None:
                details["eta_seconds"] = eta
        
        return self.create_progress_message(
            progress=progress,
            stage=stage,
            details=details
        )
    #endregion