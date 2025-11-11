import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, Optional
import aiofiles

from src.config.app_config import settings
from src.utils.files_utils import get_file_extension_by_content_type
from src.transport.rabbitmq.producer import RPCProducer
from src.utils.sse_utils import format_sse_progress, format_sse_success, format_sse_error

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


class MLProcessingService:
    """Сервис для обработки файлов через ML с поддержкой SSE."""
    
    async def process_file_with_progress(
        self, 
        file_name: str, 
        file_path: str
    ) -> AsyncIterator[str]:
        """
        Обрабатывает файл через ML сервис с генерацией SSE событий.
        
        :param file_name: Имя файла без расширения
        :param file_path: Путь к файлу
        :yields: SSE события от ML сервиса
        """
        # Пока ML сервис не реализовал execute_stream, используем заглушку
        # После реализации в ml_service.py метода execute_stream, этот код будет заменен
        
        # TODO: Заменить на прямой вызов MLService.execute_stream()
        # from src.services.ml_service.ml_service import MLService
        # ml_service = MLService()
        # async for event in ml_service.execute_stream({"name": file_name, "path": file_path}):
        #     yield event
        
        # Временная заглушка - отправка через RabbitMQ
        from src.services.stage_config_loader import get_stage_definition_for_service
        stage_definition = get_stage_definition_for_service('ml')
        
        # Отправляем события по этапам из конфигурации
        for stage in stage_definition.get_service_stages():
            yield format_sse_progress(
                progress=stage.progress,
                stage=stage.id
            )
            await asyncio.sleep(0.5)  # Задержка для демонстрации
        
        # Реальная обработка через RabbitMQ (без прогресса)
        producer = RPCProducer()
        await producer.connect()
        
        await producer.call(
            method="ml.execute",
            params={
                "data": {
                    "name": file_name,
                    "path": file_path
                }
            },
            timeout=240.0
        )


class SSEUploadOrchestrator:
    """Оркестратор для SSE загрузки файлов."""
    
    def __init__(self):
        self.file_service = FileUploadService()
        self.ml_service = MLProcessingService()
    
    async def upload_with_progress(self, file, session: Dict[str, Any]) -> AsyncIterator[str]:
        """
        Основной процесс загрузки файла с SSE прогрессом.
        
        :param file: Загруженный файл
        :param session: Сессия пользователя
        :yields: SSE события от сервисов
        """
        temp_file_path = None
        file_id = None
        
        try:
            # 1. Валидация состояния сессии (ДО установки pending=True!)
            validation_error = self.file_service.validate_session_state(session)
            if validation_error:
                error_code, error_message = validation_error.split(":", 1)
                
                # НЕ устанавливаем pending=True если валидация не прошла
                # Это позволит пользователю повторить запрос после исправления проблемы
                yield format_sse_error(
                    error_code=error_code,
                    error_message=error_message,
                    stage_failed="validation",
                    recoverable=True  # Ошибка валидации - можно повторить после исправления
                )
                return
            
            # Только после успешной валидации устанавливаем pending
            session['pending'] = True
            
            # 2. Инициализация
            yield format_sse_progress(
                progress=0,
                stage="initializing"
            )
            
            # 3. Сохранение файла
            file_id, temp_file_path = await self.file_service.save_uploaded_file(file, session)
            
            # 4. Очистка предыдущих файлов
            await self.file_service.cleanup_previous_file(session)
            
            # 5. Обработка через ML - проксируем все события от сервиса
            file_name_without_ext = os.path.splitext(file.filename)[0] if file.filename else file_id
            
            # Проксируем все SSE события от ML сервиса
            async for sse_event in self.ml_service.process_file_with_progress(file_name_without_ext, temp_file_path):
                yield sse_event
            
            # 6. Сохранение метаданных
            self.file_service.save_file_metadata(
                session=session,
                file_id=file_id,
                filename=file.filename,
                file_path=temp_file_path,
                content_type=file.content_type,
                size=file.size
            )
            
            session['pending'] = False
            session['need_download'] = True
            
            # 7. Финальное сообщение об успехе
            yield format_sse_success(
                result={
                    "file_id": file_id,
                    "file_path": temp_file_path,
                    "filename": file.filename
                }
            )
            
            logger.info(f"SSE upload completed: {file.filename}")
            
        except Exception as e:
            logger.error(f"Error in SSE upload orchestrator: {e}", exc_info=True)
            
            # Cleanup при ошибке
            if session:
                session['pending'] = False
                session['need_download'] = False
                if temp_file_path:
                    await self.file_service.cleanup_temp_file(temp_file_path, session)
            
            yield format_sse_error(
                error_code="PROCESSING_ERROR",
                error_message="Ошибка обработки файла",
                stage_failed="processing",
                error_details=str(e)
            )