"""
Тест MLService - синхронный и асинхронный (SSE) режимы.
"""

import logging
import asyncio
from src.services.ml_service.ml_service import MLService

# Настройка базового логгера
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_sync():
    """Тест синхронного режима."""
    ml_service = MLService()
    data = {'path': 'var/data_ocr/small_sample.mp4'}
    logger.info("Запуск MLService.execute с данными: %s", data)
    result = ml_service.execute(data)
    logger.info("Результат: %s", result)
    return result


async def test_stream():
    """Тест SSE streaming режима."""
    ml_service = MLService()
    data = {'path': 'var/data_ocr/small_sample.mp4'}
    logger.info("Запуск MLService.execute_stream с данными: %s", data)
    
    async for msg in ml_service.execute_stream(data):
        logger.info("SSE Message: %s", msg)
        
        # Проверяем статус
        status = msg.get("status")
        if status == "success":
            logger.info("✅ Обработка завершена успешно!")
            logger.info("Результат: %s", msg.get("result"))
            break
        elif status == "error":
            logger.error("❌ Ошибка: %s", msg.get("error"))
            break


if __name__ == '__main__':
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "stream"
    
    if mode == "sync":
        test_sync()
    else:
        asyncio.run(test_stream())
