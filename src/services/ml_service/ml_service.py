"""
Сервис перевода видео.
"""
import os
import asyncio
import shutil
import logging
from typing import AsyncIterator
from src.services.base_service import BaseService
from src.config.services.ml_config import settings, Settings
from . import utils as service_utils
from . import n_models as models
from contextlib import contextmanager
from time import perf_counter

@contextmanager
def log_duration(message: str):
    logger.info(f"⌛{message}")
    start = perf_counter()
    yield
    end = perf_counter()
    logger.info(f"Время выполнения: {end - start:.4f} сек")



logger = logging.getLogger(__name__)

# def copy_file_to_directory(source_path, target_directory):
#     """
#     Копирует файл из source_path в target_directory.
    
#     :param source_path: путь к исходному файлу
#     :param target_directory: путь к целевой директории
#     """
#     try:
#         # Проверяем, существует ли исходный файл
#         if not os.path.isfile(source_path):
#             print(f"Исходный файл не найден: {source_path}")
#             return
        
#         # Проверяем, существует ли целевая директория
#         if not os.path.isdir(target_directory):
#             print(f"Целевая директория не найдена, создаем: {target_directory}")
#             os.makedirs(target_directory)
        
#         # Формируем путь для файла в целевой директории
#         destination_path = os.path.join(target_directory, os.path.basename(source_path))
        
#         # Копируем файл
#         shutil.copy(source_path, destination_path)
#         print(f"Файл успешно скопирован в: {destination_path}")
#     except Exception as e:
#         print(f"Произошла ошибка: {e}")

# def move_file(source_dir, dest_dir, filename):
#     source_path = os.path.join(source_dir, filename)
#     dest_path = os.path.join(dest_dir, filename)
    
#     try:
#         shutil.move(source_path, dest_path)
#         print(f"Файл '{filename}' успешно перемещен из '{source_dir}' в '{dest_dir}'.")
#     except FileNotFoundError:
#         print(f"Файл '{filename}' не найден в директории '{source_dir}'.")
#     except Exception as e:
#         print(f"Произошла ошибка: {e}")
        
# def clean_directory(directory, allowed_items):
#     for item in os.listdir(directory):
#         item_path = os.path.join(directory, item)
#         if item not in allowed_items:
#             try:
#                 if os.path.isfile(item_path) or os.path.islink(item_path):
#                     os.remove(item_path)
#                     print(f"Удалён файл: {item_path}")
#                 elif os.path.isdir(item_path):
#                     shutil.rmtree(item_path)
#                     print(f"Удалена папка: {item_path}")
#             except Exception as e:
#                 print(f"Ошибка при удалении {item_path}: {e}")



class MLService(BaseService):
    """
    Сервис для обработки видео с применением ML-пайплайна.

    Этот класс выполняет последовательную обработку видео, включающую:
      - разбиение видео на кадры;
      - извлечение и распознавание аудио;
      - перевод текста;
      - синтез нового аудио;
      - обработку кадров;
      - сборку финального видео с обновлённым звуком и кадрами.

    Атрибуты:
        translate (Callable): Функция или объект для перевода текста.
        spech_recognize (Callable): Функция или объект для распознавания речи.
        ocr (Callable): Функция или объект для оптического распознавания текста (OCR).
        tts (Callable): Функция или объект для синтеза речи (Text-to-Speech).
        temp_dir (str): Временная директория для промежуточных файлов.
    """

    def __init__(self, temp_dir=settings.TEMP_DIR):
        """
        Инициализация ML-сервиса.

        Args:
            temp_dir (str): Путь к временной директории для хранения промежуточных данных.
        """
        super().__init__()
        self.audio_extract_name = 'audio_extract'
        self.audio_translate_name = 'audio_translate'
        self.audio_results_name = 'audio_results'

        self.video_ocr_name = 'video_ocr'
        self.video_translate_name = 'video_translate'

        with log_duration("INIT models"):
            self._init_models()
            
        self.temp_dir = temp_dir

    def _init_models(self):
        with log_duration("UniversalTranslator.__init__"):
            self.translator = models.UniversalTranslator(settings.TRANSLATOR_NAME, device=settings.TRANSLATOR_DEVICE, model_type=settings.TRANSLATOR_TYPE)
        
        with log_duration("SimpleWhisper.__init__"):
            self.recognizer = models.SimpleWhisper(device=settings.RECOGNIZER_DEVICE, model_name=settings.RECOGNIZER_NAME)

        with log_duration("TextToSpeech.__init__"):
            self.generator = models.TextToSpeech()

        with log_duration("OCR.__init__"):
            self.ocr = models.OCR(device=settings.OCR_DEVICE)

    def execute(self, data: dict) -> dict:
        """
        Основной метод для запуска пайплайна обработки видео.

        Args:
            data (dict): Входные данные с ключами:
                - "path" (str): Путь к исходному видео.
                - "name" (str): Имя видео (без расширения).
                - "res_dir" (str, optional): Папка для сохранения результата.
                - "message" (str, optional): Служебное сообщение.

        Returns:
            dict: Результат выполнения с ключами:
                - "status" (str): Статус выполнения ("success" или "error").
                - "message" (str): Сообщение о результате.
                - "echo" (dict): Исходные данные.
                - "service" (str): Имя сервиса.
        """
        logger.info(f"MLService.execute called with data: {data}")
        message = data.get("message", "No message provided")
        path = data.get("path", '')

        filename = os.path.basename(path)
        name = os.path.splitext(filename)[0]
        dir_path = os.path.join(self.temp_dir, name)
        os.makedirs(dir_path, exist_ok=True)

        if not path:
            logging.info("❌ Путь или имя видео не указано")
            return {"status": "error", "message": "Path missing"}

        # Запуск пайплайна обработки видео
        with log_duration(f'Обработка видео {name}'):
            resp: service_utils.Response = self.__process_video(path, name, dir_path)

        if resp.status is False:
            return {"status": "error", "message": resp.error}

        result = {
            "status": "success",
            "message": f"Data received: {message}",
            "echo": data,
            "service": self.getName()
        }

        logger.info(f"MLService.execute returning: {result}")
        return result

    async def execute_stream(self, data: dict) -> AsyncIterator[dict]:
        """
        Streaming версия execute() для SSE.
        """
        self._start_tracking()

        try:
            path = data['data']["path"]
            filename = os.path.basename(path)
            name = os.path.splitext(filename)[0]
            dir_path = os.path.join(self.temp_dir, name)
            os.makedirs(dir_path, exist_ok=True)

            # Основной streaming-пайплайн
            async for msg in self.__process_video_stream(path, name, dir_path):
                yield msg

            # Успешное завершение
            yield self.create_success_message(
                result={"output": f"{name}.mp4"}
            )

        except Exception as e:
            logger.exception("❌ Ошибка в execute_stream")
            yield self.create_error_message(
                error_code="ML_PROCESSING_FAILED",
                error_message=str(e),
                stage_failed=self._current_stage_id or "unknown"
            )

    async def __process_video_stream(self, path: str, name: str, result_dir: str):
        """
        Streaming версия обработки видео с прогрессом.
        """

        base_dir = os.path.join(self.temp_dir, name)
        extract_audio_path = os.path.join(base_dir, f'{self.audio_extract_name}.mp3')
        frames_output_dir = os.path.join(base_dir, 'frames')

        # === ЭТАП 1: copying_file ===
        self.next_stage()
        yield self.get_current_stage_message()

        shutil.copy(path, base_dir)

        # === ЭТАП 2: splitting_frames ===
        self.next_stage()
        yield self.get_current_stage_message()

        r = service_utils.extract_frames(path, frames_output_dir)
        if not r.status:
            raise Exception(r.error)

        images = service_utils.get_image_paths(frames_output_dir)

        # === ЭТАП 3: extracting_audio ===
        self.next_stage()
        yield self.get_current_stage_message()

        r = service_utils.extract_audio(path, extract_audio_path)
        if not r.status:
            raise Exception(r.error)

        # === ЭТАП 4: recognizing_speech ===
        self.next_stage()
        yield self.get_current_stage_message()

        r = self.recognizer.transcribe(extract_audio_path)
        if not r.status:
            raise Exception(r.error)
        transcript = r.result

        # === ЭТАП 5: translating_text ===
        self.next_stage()
        yield self.get_current_stage_message()

        r = self.translator.translate(transcript)
        if not r.status:
            raise Exception(r.error)
        translation = r.result

        # === ЭТАП 6: generating_tts ===
        self.next_stage()
        yield self.get_current_stage_message()

        wav_path = os.path.join(base_dir, f'{self.audio_translate_name}.wav')
        mp3_path = os.path.join(base_dir, f'{self.audio_translate_name}.mp3')

        r = self.generator.synthesize(translation, output_path=wav_path)
        if not r.status:
            raise Exception(r.error)

        service_utils.wav_to_mp3(wav_path, mp3_path)

        # === ЭТАП 7: processing_frames (С ПОДЭТАПАМИ) ===
        self.next_stage(total_substeps=len(images))

        ocr_raw = self.ocr.batch(images).result
        ocr_results = self.ocr.ocr_to_dict(ocr_raw)
        ocr_results
        translated = service_utils.translate_ocr_results(
            self.translator, ocr_results
        ).result

        out_dir = os.path.join(base_dir, "frames_translated")
        os.makedirs(out_dir, exist_ok=True)

        for img in images:
            service_utils.translate_images(
                [img], translated, output_dir=out_dir, font_path="arial.ttf"
            )
            self.increment_substep()
            yield self.get_current_stage_message(include_eta=True)

        # === ЭТАП 8: assembling_video ===
        self.next_stage()
        yield self.get_current_stage_message()

        service_utils.create_video_with_new_audio(
            images_dir=out_dir,
            original_video_path=path,
            new_audio_path=mp3_path,
            output_video_path=os.path.join(self.temp_dir, f"{name}.mp4")
        )


    def __process_video(self, path: str, name: str, result_dir: str) -> dict:
        """
        Проводит весь цикл обработки видео: извлечение, преобразование и сборка результата.

        Этапы:
            1. Разбиение видео на кадры.
            2. Извлечение аудио.
            3. Распознавание речи.
            4. Перевод текста.
            5. Генерация переведённого аудио.
            6. Обработка кадров.
            7. Переименование исходного видео.
            8. Сборка нового видео с синхронизацией аудио.

        Args:
            path (str): Путь к исходному видеофайлу.
            name (str): Имя видео (используется как префикс временных файлов).
            result_dir (str): Путь к директории для сохранения результатов.

        Returns:
            dict: Словарь с результатом выполнения:
                - "status" (bool): Успешность операции.
                - "error" (str, optional): Сообщение об ошибке (если есть).
        """
        # Основная логика обработки файла

        filename = os.path.basename(path)
        name = os.path.splitext(filename)[0]
        dir_path = os.path.join(self.temp_dir, name)
        os.makedirs(dir_path, exist_ok=True)

        extract_audio_path = os.path.join(self.temp_dir, name, f'{self.audio_extract_name}.mp3')
        frames_output_dir = os.path.join(self.temp_dir, name, 'frames')

        with log_duration("Предобработка"):
            resp: service_utils.Response = service_utils.extract_audio(path, extract_audio_path)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None) 
            
            resp: service_utils.Response = service_utils.extract_frames(path, frames_output_dir)   
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)          

        with log_duration("Обработка"):
            resp: service_utils.Response = self._audio_process(path, self.temp_dir, name)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None) 
            
            resp: service_utils.Response = self._video_process(path, self.temp_dir, name)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None) 

        images_dir=os.path.join(self.temp_dir, name, 'frames_translated')
        original_video_path = path
        new_audio_path = os.path.join(self.temp_dir, name, f'{self.audio_translate_name}.mp3')
        output_video_path=os.path.join(self.temp_dir, f'{name}.mp4')

        with log_duration("Постобработка"):
            resp:service_utils.Response = service_utils.create_video_with_new_audio(    
                images_dir=images_dir,
                original_video_path=original_video_path,
                new_audio_path=new_audio_path,
                output_video_path=output_video_path
            )
            if resp.status is False:
                return service_utils.Response(False, resp.error, None) 
        try:
            shutil.rmtree(dir_path)
            logger.info(f"✅Директория '{dir_path}' успешно удалена.")
        except FileNotFoundError:
            logger.info(f"❌Директория '{dir_path}' не найдена.")
        except Exception as e:
            logger.info(f"❌Ошибка при удалении директории: {e}")
        
        return service_utils.Response(True, None, None)
    
    def _audio_process(self, path, temp_dir, name):
        base_dir = os.path.join(temp_dir, name)
        extract_audio_path = os.path.join(base_dir, f"{self.audio_extract_name}.mp3")
        translated_wav = os.path.join(base_dir, f"{self.audio_translate_name}.wav")
        translated_mp3 = os.path.join(base_dir, f"{self.audio_translate_name}.mp3")

        with log_duration("SimpleWhisper.transcribe"):
            resp: service_utils.Response = self.recognizer.transcribe(extract_audio_path)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
            transcript = resp.result
            path = os.path.join(temp_dir, name, f"audio_text_transcript.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(transcript)
            
        with log_duration("Translator.translate"):
            resp: service_utils.Response = self.translator.translate(transcript)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
            translation = resp.result
            path = os.path.join(temp_dir, name, f"audio_text_translation.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(translation)

        with log_duration("TextToSpeech.synthesize"):
            resp: service_utils.Response = self.generator.synthesize(translation, output_path=translated_wav)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)

        with log_duration("wav_to_mp3"):
            resp: service_utils.Response = service_utils.wav_to_mp3(translated_wav, translated_mp3)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
        
        return service_utils.Response(True, None, None)

    def _video_process(self, path, temp_dir, name):
        frames_dir = os.path.join(temp_dir, name, 'frames')
        images = service_utils.get_image_paths(frames_dir)
        output_dir = os.path.join(temp_dir, name, 'frames_translated')
        ocr_out_path = os.path.join(temp_dir, name, f'ocr.json')

        with log_duration("OCR"):
            resp: service_utils.Response = self.ocr.batch(images)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
            results = resp.result

            resp: service_utils.Response = self.ocr.save_results_to_json(results, ocr_out_path)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
    
        with log_duration("Translate"):
            results = service_utils.load_json(ocr_out_path)
            resp: service_utils.Response = service_utils.translate_ocr_results(self.translator, results)
            if resp.status is False:
                return service_utils.Response(False, resp.error, None)
            translated_data = resp.result
            service_utils.save_json(translated_data, os.path.join(temp_dir, name, 'video_text.json'))

        with log_duration('Re translate'):
            resp: service_utils.Response = service_utils.translate_images(
                images,
                translated_data,
                output_dir=output_dir,
                font_path="arial.ttf"
            )
            if resp.status is False:
                return service_utils.Response(False, resp.error, None) 
        
        return service_utils.Response(True, None, None)