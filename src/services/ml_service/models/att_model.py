import logging
import whisper
from src.config.services.ml_config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseSpechRecognitionModel:
    def __init__(self):
        pass
    
    def __call__(self, path: str):
        return {'status': True, 'error': 'Error description', 'text': 'some text'}
    

class WhisperSpeechRecognitionModel(BaseSpechRecognitionModel):
    def __init__(self, cache_dir=settings.MODEL_CAHCE_DIR, model_name="tiny"):
        super().__init__()
        self.model = whisper.load_model(model_name, download_root=cache_dir)
        
        self.license = 'MIT'
    
    def __call__(self, path: str):
        try:
            result = self.model.transcribe(path)
            return {'status': True, 'text': result['text']}
        except Exception as e:
            return {'status': False, 'error': str(e)}

