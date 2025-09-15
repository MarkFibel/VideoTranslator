import os
import uuid
import logging
import aiofiles
from pathlib import Path
from fastapi import UploadFile

logger = logging.getLogger(__name__)

import time
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
            time.sleep(5)  # Искусственная задержка для демонстрации csrf защиты
            logger.debug(f"File upload completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error saving file {original_filename}: {str(e)}", exc_info=True)
            raise