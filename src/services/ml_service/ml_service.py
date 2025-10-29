"""
Сервис перевода видео.
"""
import os
import shutil
import logging
from src.services.base_service import BaseService
from src.services.ml_service.ml_pipelines import (get_ocr,
                                                  get_spech_recognize,
                                                  get_translate,
                                                  get_tts)
from src.services.ml_service.utils import (split_video_to_frames,
                                           extract_audio_from_video,
                                           images_to_video_with_audio_auto_fps,
                                           tr_frames,
                                           rename_file)
from src.config.services.ml_config import settings, Settings




logger = logging.getLogger(__name__)

def copy_file_to_directory(source_path, target_directory):
    """
    Копирует файл из source_path в target_directory.
    
    :param source_path: путь к исходному файлу
    :param target_directory: путь к целевой директории
    """
    try:
        # Проверяем, существует ли исходный файл
        if not os.path.isfile(source_path):
            print(f"Исходный файл не найден: {source_path}")
            return
        
        # Проверяем, существует ли целевая директория
        if not os.path.isdir(target_directory):
            print(f"Целевая директория не найдена, создаем: {target_directory}")
            os.makedirs(target_directory)
        
        # Формируем путь для файла в целевой директории
        destination_path = os.path.join(target_directory, os.path.basename(source_path))
        
        # Копируем файл
        shutil.copy(source_path, destination_path)
        print(f"Файл успешно скопирован в: {destination_path}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")

def move_file(source_dir, dest_dir, filename):
    source_path = os.path.join(source_dir, filename)
    dest_path = os.path.join(dest_dir, filename)
    
    try:
        shutil.move(source_path, dest_path)
        print(f"Файл '{filename}' успешно перемещен из '{source_dir}' в '{dest_dir}'.")
    except FileNotFoundError:
        print(f"Файл '{filename}' не найден в директории '{source_dir}'.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        
def clean_directory(directory, allowed_items):
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if item not in allowed_items:
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
                    print(f"Удалён файл: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"Удалена папка: {item_path}")
            except Exception as e:
                print(f"Ошибка при удалении {item_path}: {e}")

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
        self.translate = get_translate()
        self.spech_recognize = get_spech_recognize()
        self.ocr = get_ocr()
        self.tts = get_tts()
        self.temp_dir = temp_dir

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
        name = data.get("name", '')
        result_dir = data.get("res_dir", 'var/results')

        if not path or not name:
            logging.info("❌ Путь или имя видео не указано")
            return {"status": "error", "message": "Path or name missing"}

        # Копируем видео во временную директорию
        copy_file_to_directory(path, self.temp_dir)
        path = os.path.join(self.temp_dir, os.path.basename(path))

        # Запуск пайплайна обработки видео
        r = self.__process_video(path, name, result_dir)
        if not r['status']:
            return {"status": "error", "message": r.get('error', 'Processing failed')}

        result = {
            "status": "success",
            "message": f"Data received: {message}",
            "echo": data,
            "service": self.getName()
        }

        logger.info(f"MLService.execute returning: {result}")
        return result

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
        # --- Разбиение видео на кадры ---
        src_frames_dir = os.path.join(self.temp_dir, f'{name}_src_frames')
        r = split_video_to_frames(path, src_frames_dir)
        if not r['status']:
            logging.info(f"❌ Ошибка обработки кадров: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info(f"✅ Обработано кадров: {r['procced_frames']}")

        # --- Извлечение аудио ---
        src_audio_dir = os.path.join(self.temp_dir, f'{name}.mp3')
        r = extract_audio_from_video(path, src_audio_dir)
        if not r['status']:
            logging.info(f"❌ Ошибка извлечения аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info("✅ Аудио успешно извлечено")

        # --- Распознавание речи ---
        r = self.spech_recognize(src_audio_dir)
        if not r['status']:
            logging.info(f"❌ Ошибка распознавания аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        text_from_audio = r['text']
        logging.info(f"✅ Распознанный текст: {text_from_audio[:100]}...")

        # --- Перевод текста ---
        r = self.translate(text_from_audio)
        if not r['status']:
            logging.info(f"❌ Ошибка перевода: {r['error']}")
            return {'status': False, 'error': r['error']}
        translated_text = r['text']
        logging.info(f"✅ Текст переведён: {translated_text[:100]}...")

        # --- Синтез переведённого аудио ---
        translated_audio_dir = f'{name}_translated'
        r = self.tts(translated_text, translated_audio_dir)
        if not r['status']:
            logging.info(f"❌ Ошибка синтеза аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info("✅ Генерация переведённого аудио завершена")

        # --- Обработка кадров ---
        translated_frames_dir = os.path.join(self.temp_dir, f'{name}_translated_frames')
        r = tr_frames(src_frames_dir, res_dir=translated_frames_dir)
        if not r['status']:
            logging.info(f"❌ Ошибка обработки кадров: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info("✅ Перевод кадров завершён")

        # --- Переименование исходного видео ---
        file_name = os.path.basename(path)
        r = rename_file(self.temp_dir, file_name, f'temp_{file_name}')
        if not r['status']:
            logging.info(f"❌ Ошибка переименования: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info("✅ Файл переименован")

        # --- Сборка нового видео ---
        r = images_to_video_with_audio_auto_fps(
            os.path.join(self.temp_dir, f'{name}_translated_frames'),
            os.path.join(self.temp_dir, f'{name}_translated.wav'),
            os.path.join(self.temp_dir, file_name),
            path.replace(file_name, f'temp_{file_name}')
        )
        if not r['status']:
            logging.info(f"❌ Ошибка сборки видео: {r['error']}")
            return {'status': False, 'error': r['error']}
        logging.info("✅ Сборка видео завершена")

        # --- Очистка временных файлов ---
        clean_directory(self.temp_dir, [file_name, f'temp_{file_name}'])
        logging.info("🧹 Временные файлы удалены")

        return {'status': True}
