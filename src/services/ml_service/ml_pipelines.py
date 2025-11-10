
from src.services.ml_service.models.att_model import WhisperSpeechRecognitionModel
from src.services.ml_service.models.ttt_model import OpusTextTranslationModel
from src.services.ml_service.models.tts_model import VitsAudioGenerationModel


def get_translate():
    return OpusTextTranslationModel()

def get_spech_recognize():
    return WhisperSpeechRecognitionModel()

def get_ocr():
    pass

def get_tts():
    return VitsAudioGenerationModel()


