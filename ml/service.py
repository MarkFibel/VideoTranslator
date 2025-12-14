import argparse
import os
import shutil
from .utils.video import extract_frames, extract_audio, create_video_with_new_audio
from .utils.audio import wav_to_mp3
from .utils.image import translate_images
from .utils.utils import save_json, load_json, get_image_paths, translate_ocr_results, Response
from .translator import UniversalTranslator
from .speech_recognition import SimpleWhisper
from .ocr import OCR
from .audio_generator import TextToSpeech
import logging
from contextlib import contextmanager
from time import perf_counter

@contextmanager
def log_duration(message: str):
    logger.info(f"⌛{message}")
    start = perf_counter()
    yield
    end = perf_counter()
    logger.info(f"Время выполнения: {end - start:.4f} сек")



TRANSLATOR_NAME = "glazzova/translation_en_ru"
TRANSLATOR_TYPE = "marian"
TRANSLATOR_DEVICE = "mps"

RECOGNIZER_NAME = "medium"
RECOGNIZER_DEVICE = "cpu"

OCR_DEVICE = "mps"

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.audio_extract_name = 'audio_extract'
        self.audio_translate_name = 'audio_translate'
        self.audio_results_name = 'audio_results'

        self.video_ocr_name = 'video_ocr'
        self.video_translate_name = 'video_translate'

        with log_duration("INIT models"):
            self._init_models()

    def _init_models(self):
        with log_duration("UniversalTranslator.__init__"):
            self.translator = UniversalTranslator(TRANSLATOR_NAME, device=TRANSLATOR_DEVICE, model_type=TRANSLATOR_TYPE)
        
        with log_duration("SimpleWhisper.__init__"):
            self.recognizer = SimpleWhisper(device=RECOGNIZER_DEVICE, model_name=RECOGNIZER_NAME)

        with log_duration("TextToSpeech.__init__"):
            self.generator = TextToSpeech()

        with log_duration("OCR.__init__"):
            self.ocr = OCR(device=OCR_DEVICE)

    def _audio_process(self, path, temp_dir, name):
        base_dir = os.path.join(temp_dir, name)
        extract_audio_path = os.path.join(base_dir, f"{self.audio_extract_name}.mp3")
        translated_wav = os.path.join(base_dir, f"{self.audio_translate_name}.wav")
        translated_mp3 = os.path.join(base_dir, f"{self.audio_translate_name}.mp3")

        with log_duration("SimpleWhisper.transcribe"):
            resp: Response = self.recognizer.transcribe(extract_audio_path)
            if resp.status is False:
                return Response(False, resp.error, None)
            transcript = resp.result
            path = os.path.join(temp_dir, name, f"audio_text_transcript.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(transcript)
            
        with log_duration("Translator.translate"):
            resp: Response = self.translator.translate(transcript)
            if resp.status is False:
                return Response(False, resp.error, None)
            translation = resp.result
            path = os.path.join(temp_dir, name, f"audio_text_translation.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(translation)

        with log_duration("TextToSpeech.synthesize"):
            resp: Response = self.generator.synthesize(translation, output_path=translated_wav)
            if resp.status is False:
                return Response(False, resp.error, None)

        with log_duration("wav_to_mp3"):
            resp: Response = wav_to_mp3(translated_wav, translated_mp3)
            if resp.status is False:
                return Response(False, resp.error, None)
        
        return Response(True, None, None)

    def _video_process(self, path, temp_dir, name):
        frames_dir = os.path.join(temp_dir, name, 'frames')
        images = get_image_paths(frames_dir)
        output_dir = os.path.join(temp_dir, name, 'frames_translated')
        ocr_out_path = os.path.join(temp_dir, name, f'ocr.json')

        with log_duration("OCR"):
            resp: Response = self.ocr.batch(images)
            if resp.status is False:
                return Response(False, resp.error, None)
            results = resp.result

            resp: Response = self.ocr.save_results_to_json(results, ocr_out_path)
            if resp.status is False:
                return Response(False, resp.error, None)
    
        with log_duration("Translate"):
            results = load_json(ocr_out_path)
            resp: Response = translate_ocr_results(self.translator, results)
            if resp.status is False:
                return Response(False, resp.error, None)
            translated_data = resp.result
            save_json(translated_data, os.path.join(temp_dir, name, 'video_text.json'))

        with log_duration('Re translate'):
            resp: Response = translate_images(
                images,
                translated_data,
                output_dir=output_dir,
                font_path="arial.ttf"
            )
            if resp.status is False:
                return Response(False, resp.error, None) 
        
        return Response(True, None, None)

    def run(self, path, temp_dir):
        # Основная логика обработки файла
        logger.info(f"🌟Запуск обработки файла: {path} с временной директорией: {temp_dir}")
        start_process_time = perf_counter()

        filename = os.path.basename(path)
        name = os.path.splitext(filename)[0]
        dir_path = os.path.join(temp_dir, name)
        os.makedirs(dir_path, exist_ok=True)

        extract_audio_path = os.path.join(temp_dir, name, f'{self.audio_extract_name}.mp3')
        frames_output_dir = os.path.join(temp_dir, name, 'frames')

        with log_duration("Предобработка"):
            resp: Response = extract_audio(path, extract_audio_path)
            if resp.status is False:
                return Response(False, resp.error, None) 
            
            resp: Response = extract_frames(path, frames_output_dir)   
            if resp.status is False:
                return Response(False, resp.error, None)          

        with log_duration("Обработка"):
            resp: Response = self._audio_process(path, temp_dir, name)
            if resp.status is False:
                return Response(False, resp.error, None) 
            
            resp: Response = self._video_process(path, temp_dir, name)
            if resp.status is False:
                return Response(False, resp.error, None) 

        images_dir=os.path.join(temp_dir, name, 'frames_translated')
        original_video_path = path
        new_audio_path = os.path.join(temp_dir, name, f'{self.audio_translate_name}.mp3')
        output_video_path=os.path.join(temp_dir, f'{name}.mp4')

        with log_duration("Постобработка"):
            resp: Response = create_video_with_new_audio(    
                images_dir=images_dir,
                original_video_path=original_video_path,
                new_audio_path=new_audio_path,
                output_video_path=output_video_path
            )
            if resp.status is False:
                return Response(False, resp.error, None) 

        end_process_time = perf_counter()
        # shutil.copytree(os.path.join(temp_dir, name), os.path.join(temp_dir, name + '_example'))
        logger.info(f"✅Обработка файла '{path}' завершена. Общее время {end_process_time - start_process_time:.4f}")
        try:
            shutil.rmtree(dir_path)
            logger.info(f"✅Директория '{dir_path}' успешно удалена.")
        except FileNotFoundError:
            logger.info(f"❌Директория '{dir_path}' не найдена.")
        except Exception as e:
            logger.info(f"❌Ошибка при удалении директории: {e}")
        
        return Response(True, None, None)



def start():
    parser = argparse.ArgumentParser(description='Описание вашей программы')
    parser.add_argument('--source', type=str, help='Путь к входному файлу')
    parser.add_argument('--temp_dir', type=str, help='Путь к входному файлу')
    args = parser.parse_args()
    path = args.source
    temp_dir = args.temp_dir


    ml_service = MLService()
    ml_service.run(path, temp_dir)

