# Model for generating audio from text
import logging
from transformers import VitsModel, AutoTokenizer
import torch
import numpy as np
import scipy.io.wavfile as wvfile
from pydub import AudioSegment
from src.config.services.ml_config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseSpeechGenerationModel:
    def __init__(self):
        pass
    
    def __call__(self, text: str, output_path: str):
        return {'status': True, 'error': '', 'source_text': text}


class VitsAudioGenerationModel(BaseSpeechGenerationModel):
    def __init__(self, model_name="facebook/mms-tts-rus", cache_dir=settings.MODEL_CAHCE_DIR):
        self.model_name = model_name
        self.model = VitsModel.from_pretrained(model_name, cache_dir=cache_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        logger.info(f"Loaded model and tokenizer: {model_name}")
    
    def __call__(self, text: str, output_path: str, temp_dir='var/temp'):
        try:
            inputs = self.tokenizer(text, return_tensors="pt")
            with torch.no_grad():
                output = self.model(**inputs).waveform
            
            # Convert tensor to numpy and scale to int16
            waveform = output[0].cpu().numpy()
            waveform_int16 = (waveform * 32767).astype(np.int16)
            
            wav_path = f"{temp_dir}/{output_path}.wav"
            mp3_path = f"{temp_dir}/{output_path}.mp3"
            
            # Write WAV file
            wvfile.write(wav_path, rate=self.model.config.sampling_rate, data=waveform_int16)
            logger.info(f"WAV file saved to: {wav_path}")
            
            return {'status': True, 'source_text': text, 'wav_path': wav_path, 'mp3_path': mp3_path}
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return {'status': False, 'error': str(e), 'source_text': text}
