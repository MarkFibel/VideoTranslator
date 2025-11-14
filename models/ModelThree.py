import os
import time
import logging
import torch
import numpy as np
import scipy.io.wavfile as wvfile
from pydub import AudioSegment
from transformers import pipeline, AutoModelForTextToWaveform, AutoTokenizer, SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from espnet2.bin.tts_inference import Text2Speech
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseSpeechGenerationModel:
    def __init__(self):
        pass

    def __call__(self, text: str, output_basename: str, temp_dir=settings.TEMP_DIR):
        raise NotImplementedError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ESPnetFastSpeech2HiFiGANModel(BaseSpeechGenerationModel):
    def __init__(self, model_name="espnet/fastspeech2_conformer_with_hifigan", device="cpu"):
        super().__init__()
        logger.info(f"Loading: {model_name}")
        self.pipe = pipeline("text-to-audio", model=model_name, device=device)
        self.device = device

    def __call__(self, text: str, output_basename: str, temp_dir=settings.TEMP_DIR):
        os.makedirs(temp_dir, exist_ok=True)
        timings = {}
        start_total = time.time()

        # Preprocessing
        t0 = time.time()
        timings["preprocessing"] = time.time() - t0

        # Inference
        t0 = time.time()
        result = self.pipe(text)

        if isinstance(result, list) and "audio" in result[0]:
            waveform = result[0]["audio"]
            sampling_rate = result[0].get("sampling_rate", 22050)
        elif isinstance(result, dict) and "audio" in result:
            waveform = result["audio"]
            sampling_rate = result.get("sampling_rate", 22050)
        else:
            waveform = np.array(result)
            sampling_rate = 22050

        timings["inference"] = time.time() - t0

        # Postprocessing
        t0 = time.time()
        waveform_int16 = (waveform * 32767).astype(np.int16)
        wav_path = os.path.join(temp_dir, f"{output_basename}.wav")
        mp3_path = os.path.join(temp_dir, f"{output_basename}.mp3")

        if sampling_rate is None:
            sampling_rate = 22050
        wvfile.write(wav_path, rate=sampling_rate, data=waveform_int16)

        audio_segment = AudioSegment(
            waveform_int16.tobytes(),
            frame_rate=sampling_rate,
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
