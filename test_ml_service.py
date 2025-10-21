import logging
from src.services.ml_service.ml_service import MLService

# Настройка базового логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    ml_service = MLService('var/temp')
    data = {'path': 'var/data/sample.mp4'}
    logger.info("Запуск MLService.execute с данными: %s", data)
    ml_service.execute(data)