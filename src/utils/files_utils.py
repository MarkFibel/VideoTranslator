import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_file_extension_by_name(filename: str) -> str:
    """
    Возвращает расширение файла из его имени.
    
    :param filename: Имя файла.
    :return: Расширение файла (без точки), или пустая строка, если расширение отсутствует.
    """
    parts = filename.rsplit('.', 1)
    if len(parts) == 2:
        return parts[1].lower()
    return ''


def get_file_extension_by_content_type(content_type: str) -> str:
    """
    Возвращает расширение файла по его MIME типу.
    
    :param content_type: MIME тип файла.
    :return: Расширение файла (без точки), или пустая строка, если тип неизвестен.
    """
    mime_to_extension = {
        "video/x-matroska": "mkv",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/quicktime": "mov",
    }
    return mime_to_extension.get(content_type, '')


def cleanup_session_file(session_id: str, session_data: dict) -> None:
    """
    Удаляет временный файл, связанный с сессией.
    
    Эта функция вызывается как callback при удалении сессии.
    Она проверяет наличие метаданных о загруженном файле в данных сессии
    и удаляет соответствующий физический файл из файловой системы.
    
    :param session_id: ID сессии
    :param session_data: Данные сессии (словарь)
    """
    file_metadata = session_data.get('last_uploaded_file')
    
    if not file_metadata:
        logger.debug(f"Session {session_id} has no uploaded file")
        return
    
    file_path = file_metadata.get('file_path')
    
    if not file_path:
        logger.warning(f"Session {session_id} has file metadata but no file_path")
        return
    
    # Проверяем существование файла
    if not os.path.exists(file_path):
        logger.warning(f"File not found for cleanup: {file_path} (session: {session_id})")
        return
    
    # Удаляем файл
    try:
        os.remove(file_path)
        logger.info(
            f"Deleted temp file: {file_path} "
            f"(session: {session_id}, filename: {file_metadata.get('filename')})"
        )
    except OSError as e:
        logger.error(f"Failed to delete file {file_path}: {e}", exc_info=True)


def cleanup_orphaned_files(temp_dir: str, max_age_hours: int = 24) -> int:
    """
    Удаляет файлы старше max_age_hours из TEMP_DIR.
    Вызывается при старте приложения для очистки "осиротевших" файлов.
    
    :param temp_dir: Путь к директории с временными файлами
    :param max_age_hours: Максимальный возраст файлов в часах
    :return: Количество удаленных файлов
    """
    if not os.path.exists(temp_dir):
        logger.info(f"Temp directory does not exist: {temp_dir}")
        return 0
    
    current_time = time.time()
    cutoff_time = current_time - (max_age_hours * 3600)
    deleted_count = 0
    
    try:
        for file_path in Path(temp_dir).iterdir():
            if file_path.is_file():
                try:
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Removed orphaned file: {file_path}")
                except OSError as e:
                    logger.warning(f"Failed to remove orphaned file {file_path}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error during orphaned files cleanup: {e}", exc_info=True)
    
    if deleted_count > 0:
        logger.info(f"Startup cleanup: removed {deleted_count} orphaned files from {temp_dir}")
    else:
        logger.info(f"Startup cleanup: no orphaned files found in {temp_dir}")
    
    return deleted_count