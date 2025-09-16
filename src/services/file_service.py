import os
import uuid
import logging
import aiofiles
import asyncio
from pathlib import Path
from fastapi import UploadFile
from typing import Dict, Optional

from .background_task_service import background_task_service

logger = logging.getLogger(__name__)


class FileService:
    
    def __init__(self) -> None:
        self.upload_dir = Path("var/temp")
        # Убедимся, что директория существует
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileService initialized. Upload directory: {self.upload_dir.absolute()}")
    
    async def upload(self, file: UploadFile) -> dict:
        """
        Сохраняет загруженный файл в директорию var/temp с UUID именем
        
        Args:
            file: Загружаемый файл
            
        Returns:
            dict: Информация о сохраненном файле
        """
        logger.debug(f"Starting file upload process for: {file.filename}")
        
        # Генерируем UUID для имени файла
        file_uuid = str(uuid.uuid4())
        
        # Получаем расширение оригинального файла
        original_filename = file.filename or "unknown"
        file_extension = Path(original_filename).suffix
        
        # Создаем имя файла с UUID и оригинальным расширением
        local_filename = f"{file_uuid}{file_extension}"
        file_path = self.upload_dir / local_filename
        
        logger.debug(f"Generated UUID: {file_uuid}, Local filename: {local_filename}")
        
        try:
            # Сохраняем файл
            async with aiofiles.open(file_path, 'wb') as buffer:
                content = await file.read()
                await buffer.write(content)
            
            logger.info(f"File saved successfully: {file_path}, Size: {len(content)} bytes")
            
            # Возвращаем информацию о сохраненном файле
            result = {
                "uuid": file_uuid,
                "original_filename": original_filename,
                "local_filename": local_filename,
                "file_path": str(file_path),
                "content_type": file.content_type,
                "size": len(content)
            }
            
            logger.debug(f"File upload completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error saving file {original_filename}: {str(e)}", exc_info=True)
            raise

    async def process_file_async(self, task_id: str, file_info: Dict) -> Dict:
        """
        Асинхронная обработка файла с отправкой обновлений прогресса
        
        Args:
            task_id: ID задачи для отправки обновлений прогресса
            file_info: Информация о файле из upload()
            
        Returns:
            dict: Результат обработки файла
        """
        logger.info(f"Starting async file processing for task: {task_id}")
        
        try:
            # Симуляция обработки с обновлениями прогресса
            stages = [
                (10, "Проверка файла..."),
                (25, "Анализ содержимого..."),
                (50, "Обработка данных..."),
                (75, "Применение алгоритмов..."),
                (90, "Финализация результата..."),
                (100, "Обработка завершена")
            ]
            
            for progress, message in stages:
                await background_task_service.send_progress_update(task_id, progress, message)
                await asyncio.sleep(1)  # Симуляция времени обработки
            
            # Результат обработки
            processing_result = {
                "task_id": task_id,
                "file_uuid": file_info["uuid"],
                "original_filename": file_info["original_filename"],
                "processing_status": "completed",
                "processed_file_path": file_info["file_path"].replace(".mp4", "_processed.mp4"),
                "processing_duration": len(stages),  # В секундах
                "output_size": file_info["size"] * 1.1,  # Симуляция изменения размера
                "processing_details": {
                    "algorithm_applied": "video_translation_v2",
                    "source_language": "auto_detected",
                    "target_language": "ru",
                    "quality": "high"
                }
            }
            
            logger.info(f"File processing completed successfully for task: {task_id}")
            return processing_result
            
        except Exception as e:
            logger.error(f"Error processing file for task {task_id}: {str(e)}", exc_info=True)
            raise

    async def upload_and_start_processing(self, file: UploadFile, client_id: str) -> tuple[Dict, str]:
        """
        Загружает файл и запускает фоновую обработку
        
        Args:
            file: Загружаемый файл
            client_id: ID клиента для SSE уведомлений
            
        Returns:
            tuple: (информация о файле, task_id)
        """
        # Сначала загружаем файл
        file_info = await self.upload(file)
        
        # Запускаем фоновую обработку
        task_id = await background_task_service.submit_task(
            client_id,
            "file_processing",
            self.process_file_async,
            file_info
        )
        
        logger.info(f"File uploaded and processing started. Task ID: {task_id}")
        return file_info, task_id