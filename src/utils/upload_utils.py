import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import aiofiles

from src.config.app_config import settings
from src.utils.files_utils import get_file_extension_by_content_type

logger = logging.getLogger(__name__)


class FileUploadService:
    """Сервис для загрузки и обработки файлов."""
    
    async def save_uploaded_file(self, file, session: Dict[str, Any]) -> tuple[str, str]:
        """
        Сохраняет загруженный файл во временную директорию.
        
        :param file: Загруженный файл
        :param session: Сессия пользователя
        :return: (file_id, temp_file_path)
        """
        temp_dir = settings.TEMP_DIR
        
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        file_id = uuid.uuid4().hex
        file_ext = get_file_extension_by_content_type(
            file.content_type if file.content_type else ""
        )
        
        file_tmp_name = f"{file_id}.{file_ext}" if file_ext else file_id
        temp_file_path = os.path.join(temp_dir, file_tmp_name)
        
        # Асинхронная запись файла
        async with aiofiles.open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            await temp_file.write(content)
        
        logger.info(f"File saved: {temp_file_path} (size: {file.size} bytes)")
        
        return file_id, temp_file_path
    
    async def save_uploaded_file_from_bytes(
        self, content: bytes, metadata: Dict[str, Any], session: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Сохраняет файл из bytes во временную директорию.
        Используется для StreamingResponse, где файл нужно прочитать заранее.
        
        :param content: Содержимое файла в bytes
        :param metadata: Метаданные файла (content_type, filename, size)
        :param session: Сессия пользователя
        :return: (file_id, temp_file_path)
        """
        temp_dir = settings.TEMP_DIR
        
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        file_id = uuid.uuid4().hex
        content_type = metadata.get("content_type", "")
        file_ext = get_file_extension_by_content_type(content_type)
        
        file_tmp_name = f"{file_id}.{file_ext}" if file_ext else file_id
        temp_file_path = os.path.join(temp_dir, file_tmp_name)
        
        # Асинхронная запись файла
        async with aiofiles.open(temp_file_path, "wb") as temp_file:
            await temp_file.write(content)
        
        file_size = metadata.get("size") or len(content)
        logger.info(f"File saved from bytes: {temp_file_path} (size: {file_size} bytes)")
        
        return file_id, temp_file_path
    
    async def cleanup_previous_file(self, session: Dict[str, Any]) -> None:
        """Удаляет предыдущий файл из сессии."""
        if session.get('last_uploaded_file'):
            previous_file_path = session['last_uploaded_file'].get("file_path", "")
            
            if previous_file_path and os.path.exists(previous_file_path):
                try:
                    await asyncio.to_thread(os.remove, previous_file_path)
                    session['last_uploaded_file'] = None
                    logger.info(f"Previous file removed: {previous_file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to remove previous file {previous_file_path}: {e}"
                    )
    
    async def cleanup_temp_file(self, file_path: str, session: Dict[str, Any]) -> None:
        """Удаляет временный файл при ошибке."""
        if file_path and os.path.exists(file_path):
            try:
                await asyncio.to_thread(os.remove, file_path)
                logger.info(f"Temp file removed: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp file {file_path}: {e}")
        
        session['last_uploaded_file'] = None
    
    def validate_session_state(self, session: Dict[str, Any]) -> Optional[str]:
        """
        Валидирует состояние сессии для загрузки файла.
        
        :param session: Сессия пользователя
        :return: Сообщение об ошибке или None если все OK
        """
        if session.get('pending', False):
            return "FILE_PROCESSING:Файл уже в процессе обработки"
        
        if session.get('need_download', False):
            return "FILE_DOWNLOAD_PENDING:Скачайте предыдущий файл перед загрузкой нового"
        
        return None
    
    def save_file_metadata(self, session: Dict[str, Any], file_id: str, 
                          filename: str, file_path: str, content_type: str, size: int) -> None:
        """Сохраняет метаданные файла в сессию."""
        session['last_uploaded_file'] = {
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "content_type": content_type,
            "size": size,
            "upload_time": datetime.now(timezone.utc).isoformat()
        }
