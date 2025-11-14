import os
import time
import logging
import torch
import numpy as np
import scipy.io.wavfile as wvfile
from pydub import AudioSegment
from transformers import pipeline, AutoModelForTextToWaveform, AutoTokenizer, SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from espnet2.bin.tts_inference import Text2Speech
from config import settings  # базовый settings с TEMP_DIR и MODEL_CACHE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseSpeechGenerationModel:
    def __init__(self):
        pass

    def __call__(self, text: str, output_basename: str, temp_dir=settings.TEMP_DIR):
        raise NotImplementedError
    

class ESPnetVITSModel(BaseSpeechGenerationModel):
    def __init__(self, model_name="espnet/kan-bayashi_ljspeech_vits"):
        super().__init__()
        logger.info(f"Loading: {model_name}")
        self.model = Text2Speech.from_pretrained(model_name)

    def __call__(self, text: str, output_basename: str, temp_dir=settings.TEMP_DIR):
        os.makedirs(temp_dir, exist_ok=True)
        timings = {}
        start_total = time.time()
        try:
            # Preprocessing
            t0 = time.time()
            timings["preprocessing"] = time.time() - t0

            # Inference
            t0 = time.time()
            speech, *_ = self.model(text)
            timings["inference"] = time.time() - t0

            # Postprocessing
            t0 = time.time()
            waveform_int16 = (speech.numpy() * 32767).astype(np.int16)
            wav_path = os.path.join(temp_dir, f"{output_basename}.wav")
            mp3_path = os.path.join(temp_dir, f"{output_basename}.mp3")
            wvfile.write(wav_path, rate=self.model.fs, data=waveform_int16)
            audio_segment = AudioSegment(
                waveform_int16.tobytes(),
                frame_rate=self.model.fs,
                sample_width=2,
                channels=1
            )
            audio_segment.export(mp3_path, format="mp3")
            timings["postprocessing"] = time.time() - t0
            timings["total"] = time.time() - start_total

            return {
                "status": True,
                "source_text": text,
                "wav_path": wav_path,
                "mp3_path": mp3_path,
                "timings": timings
            }
        except Exception as e:
            logger.error(f"ESPnet VITS error: {e}")

            return {"status": False, "error": str(e), "source_text": text}
