"""
Пример использования автоматического учета прогресса в BaseService.
"""

import asyncio
from typing import AsyncIterator
from src.services.base_service import BaseService


class VideoProcessingService(BaseService):
    """Пример сервиса с автоматическим отслеживанием прогресса."""
    
    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Обработка видео с РУЧНЫМ указанием этапов.
        """
        # Начинаем отслеживание времени
        self._start_tracking()
        
        try:
            # Этап 1: Загрузка видео
            self.set_stage("video_loading")
            yield self.get_current_stage_message()
            await asyncio.sleep(1)  # Имитация работы
            
            # Этап 2: Извлечение кадров (с подэтапами)
            self.set_stage("frame_extraction", total_substeps=10)
            for i in range(10):
                self.increment_substep()
                yield self.get_current_stage_message(include_eta=True)
                await asyncio.sleep(0.2)  # Имитация обработки каждого кадра
            
            # Этап 3: Распознавание текста
            self.set_stage("text_recognition", total_substeps=5)
            for i in range(5):
                self.set_substep(i + 1)
                yield self.get_current_stage_message(include_eta=True)
                await asyncio.sleep(0.3)
            
            # Этап 4: Перевод текста
            self.set_stage("text_translation")
            yield self.get_current_stage_message()
            await asyncio.sleep(1)
            
            # Этап 5: Озвучивание
            self.set_stage("audio_generation", total_substeps=3)
            for i in range(3):
                self.increment_substep()
                yield self.get_current_stage_message()
                await asyncio.sleep(0.5)
            
            # Этап 6: Финальная сборка
            self.set_stage("final_assembly")
            yield self.get_current_stage_message()
            await asyncio.sleep(1)
            
            # Успешное завершение
            yield self.create_success_message(
                result={
                    "output_file": "translated_video.mp4",
                    "duration": self._get_elapsed_time()
                }
            )
            
        except Exception as e:
            # Ошибка
            yield self.create_error_message(
                error_code="PROCESSING_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown",
                error_details=f"Error occurred after {self._get_elapsed_time():.2f}s"
            )


class AutoVideoProcessingService(BaseService):
    """Пример сервиса с АВТОМАТИЧЕСКИМ переключением этапов."""
    
    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Обработка видео с автоматическим переключением этапов из YAML конфигурации.
        """
        self._start_tracking()
        
        try:
            # Этап 1: Загрузка видео (автоматически берется из YAML)
            self.next_stage()
            yield self.get_current_stage_message()
            await asyncio.sleep(1)
            
            # Этап 2: Извлечение кадров (автоматический переход + подэтапы)
            self.next_stage(total_substeps=10)
            for i in range(10):
                self.increment_substep()
                yield self.get_current_stage_message(include_eta=True)
                await asyncio.sleep(0.2)
            
            # Этап 3: Распознавание текста (автоматический переход)
            self.next_stage(total_substeps=5)
            for i in range(5):
                self.set_substep(i + 1)
                yield self.get_current_stage_message(include_eta=True)
                await asyncio.sleep(0.3)
            
            # Этап 4: Перевод текста (автоматический переход)
            self.next_stage()
            yield self.get_current_stage_message()
            await asyncio.sleep(1)
            
            # Этап 5: Озвучивание (автоматический переход)
            self.next_stage(total_substeps=3)
            for i in range(3):
                self.increment_substep()
                yield self.get_current_stage_message()
                await asyncio.sleep(0.5)
            
            # Этап 6: Финальная сборка (автоматический переход)
            self.next_stage()
            yield self.get_current_stage_message()
            await asyncio.sleep(1)
            
            # Успешное завершение
            yield self.create_success_message(
                result={
                    "output_file": "translated_video.mp4",
                    "duration": self._get_elapsed_time()
                }
            )
            
        except Exception as e:
            yield self.create_error_message(
                error_code="PROCESSING_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown",
                error_details=f"Error occurred after {self._get_elapsed_time():.2f}s"
            )


async def demo_manual_stages():
    """Демонстрация РУЧНОГО указания этапов."""
    print("=== Демонстрация РУЧНОГО указания этапов (set_stage) ===\n")
    
    service = VideoProcessingService()
    service.set_stage_definition("video_processing")
    
    async for message in service.execute_stream({"video_path": "test.mp4"}):
        _print_progress_message(message)


async def demo_auto_stages():
    """Демонстрация АВТОМАТИЧЕСКОГО переключения этапов."""
    print("\n=== Демонстрация АВТОМАТИЧЕСКОГО переключения этапов (next_stage) ===\n")
    
    service = AutoVideoProcessingService()
    service.set_stage_definition("video_processing")
    
    async for message in service.execute_stream({"video_path": "test.mp4"}):
        _print_progress_message(message)


def _print_progress_message(message: dict):
    """Вспомогательная функция для форматированного вывода."""
    if message.get("status") == "success":
        print(f"\n✓ ЗАВЕРШЕНО: {message.get('result')}")
    elif message.get("status") == "error":
        error = message.get("error", {})
        print(f"\n✗ ОШИБКА: {error.get('message')}")
    else:
        progress = message.get("progress", 0)
        stage = message.get("stage", "unknown")
        details = message.get("details", {})
        
        eta_info = ""
        if "eta_seconds" in details:
            eta_info = f" | ETA: {details['eta_seconds']}s"
        
        substep_info = ""
        if "current_step" in details:
            substep_info = f" ({details['current_step']}/{details['total_steps']})"
        
        print(f"[{progress:3d}%] {stage}{substep_info}{eta_info}")


async def demo_simple_usage():
    """Демонстрация простого использования без подэтапов."""
    print("\n=== Простое использование без подэтапов ===\n")
    
    service = VideoProcessingService()
    service.set_stage_definition("video_processing")
    service._start_tracking()
    
    # Просто переключаем этапы
    stages = ["video_loading", "frame_extraction", "text_recognition", 
              "text_translation", "audio_generation", "final_assembly"]
    
    for stage in stages:
        service.set_stage(stage)
        message = service.get_current_stage_message()
        print(f"[{message['progress']:3d}%] {message['stage']}")
        await asyncio.sleep(0.5)
    
    # Финальное сообщение
    final = service.create_success_message()
    print(f"\n✓ ЗАВЕРШЕНО: progress={final['progress']}%")


if __name__ == "__main__":
    print("Запуск демонстрации...\n")
    asyncio.run(demo_manual_stages())
    asyncio.run(demo_auto_stages())
    asyncio.run(demo_simple_usage())
