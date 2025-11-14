import logging
import time
import os
import numpy as np
import torch
import scipy.io.wavfile as wavfile
from pydub import AudioSegment

from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from config import settings


logger = logging.getLogger(__name__)


class SpeechT5GenerationModel:
    def __init__(
        self,
        model_name="microsoft/speecht5_tts",
        vocoder_name="microsoft/speecht5_hifigan",
        cache_dir=settings.MODEL_CACHE_DIR
    ):
        super().__init__()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.processor = SpeechT5Processor.from_pretrained(model_name, cache_dir=cache_dir)
        self.model = SpeechT5ForTextToSpeech.from_pretrained(model_name, cache_dir=cache_dir).to(self.device)
        self.vocoder = SpeechT5HifiGan.from_pretrained(vocoder_name, cache_dir=cache_dir).to(self.device)

        self.speaker_embedding = torch.randn(1, 512).to(self.device)

        logger.info("SpeechT5 loaded successfully")

    def __call__(self, text: str, output_basename: str, temp_dir=settings.TEMP_DIR):
        timings = {}
        os.makedirs(temp_dir, exist_ok=True)
        start = time.time()

        try:
            # preprocess
            t0 = time.time()
            inputs = self.processor(text=text, return_tensors="pt").to(self.device)
            timings["preprocessing"] = time.time() - t0

            # inference
            t0 = time.time()
            with torch.no_grad():
                spectrogram = self.model.generate_speech(inputs["input_ids"], self.speaker_embedding)
            timings["inference_specht5"] = time.time() - t0

            # vocoder
            t0 = time.time()
            with torch.no_grad():
                waveform = self.vocoder(spectrogram).cpu().numpy()
            timings["vocoder"] = time.time() - t0

            # postprocess
            t0 = time.time()
            waveform_int16 = (waveform * 32767).astype(np.int16)

            wav_path = os.path.join(temp_dir, f"{output_basename}.wav")
            mp3_path = os.path.join(temp_dir, f"{output_basename}.mp3")

            wavfile.write(wav_path, 16000, waveform_int16)
            AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3")

            timings["postprocessing"] = time.time() - t0
            timings["total"] = time.time() - start

            return {
                "status": True,
                "source_text": text,
                "wav_path": wav_path,
                "mp3_path": mp3_path,
                "timings": timings
            }

        except Exception as e:
            logger.error(f"SpeechT5 error: {e}")
            return {"status": False, "error": str(e)}

