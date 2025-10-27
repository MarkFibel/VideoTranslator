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
    Сервис для обработки видео.
    """
    
    def __init__(self, temp_dir=settings.TEMP_DIR):
        self.translate = get_translate()
        self.spech_recognize = get_spech_recognize()
        self.ocr = get_ocr()
        self.tts = get_tts()
        
        self.temp_dir = temp_dir    
    
    def execute(self, data: dict) -> dict:
        """
        Метод запуска обработки видео.
        Для запуска необходимо передать путь к видео и имя файла.
        Структура вызова через JSON-RPC:
        {
            "method": "ml.execute",
            "params": {
                "data": {
                    "path": "path/to/video",
                    "name": "video_name"
                }
            }
        }
        """

        logger.info(f"MLService.execute called with data: {data}")
        
        # Получаем параметр message из входных данных
        message = data.get("message", "No message provided")
        
        path = data.get("path", '')
        name = data.get("name", '')
        
        result_dir = data.get("res_dir", 'var/results')
        if path == '' or name == '':
            logging.info(f"Путь не распознан")
        
        copy_file_to_directory(path, self.temp_dir)
        
        path = '/'.join([self.temp_dir, os.path.basename(path)])
        
        r = self.__process_video(path, name, result_dir)
        if r['status']:
            pass
        
        # Формируем ответ
        result = {
            "status": "success",
            "message": f"Data received: {message}",
            "echo": data,
            "service": self.getName()
        }
        
        logger.info(f"MLService.execute returning: {result}")
        
        return result
    
    def __process_video(self, path: str, name: str, result_dir: str):
        #✅⚠️❌
        # Получаем кадры из видео
        src_frames_dir = '/'.join([self.temp_dir, f'{name}_src_frames'])
        r = split_video_to_frames(path, src_frames_dir)
        if r['status']:
            logging.info(f"✅ Обработано кадров: {r['procced_frames']}")
        else:
            logging.info(f"❌ произошла ошибка в обработке кадров: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Получаем аудио из видео
        src_audio_dir = '/'.join([self.temp_dir, f'{name}.mp3'])
        r = extract_audio_from_video(path, src_audio_dir)
        if r['status']:
            logging.info(f"✅ аудио успешно извлеченно")
        else:
            logging.info(f"❌ произошла ошибка в обработке аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Получаем текст из аудио
        r = self.spech_recognize(src_audio_dir)
        if r['status']:
            logging.info(f"✅ Получен текст из аудио, Текст: {r['text'][:100]}")
            text_from_audio = r['text']
        else:
            logging.info(f"❌ произошла ошибка в обработке аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Получаем переводим текст
        r = self.translate(text_from_audio)
        if r['status']:
            logging.info(f"✅ Текст переведен успешно, Текст: {r['text'][:100]}")
            translated_text_from_audio = r['text']
        else:
            logging.info(f"❌ произошла ошибка в переводе текста: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Получаем аудио из переведнного текста
        translated_audio_dir = f'{name}_translated'
        r = self.tts(translated_text_from_audio, translated_audio_dir)
        if r['status']:
            logging.info(f"✅ Генерирование аудио завершено")
        else:
            logging.info(f"❌ произошла ошибка в генерации переведнного аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Получаем перевод кадров из видео
        translated_frames_fir = '/'.join([self.temp_dir, f'{name}_translated_frames'])
        r = tr_frames(src_frames_dir, res_dir=translated_frames_fir) #TODO 
        if r['status']:
            logging.info(f"✅ Перевод фрэймов заверешен")
        else:
            logging.info(f"❌ произошла ошибка в переводе фреймов: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Изменям имя оригинального видео на имя с припиской temp
        file_name = os.path.basename(path)
        r = rename_file(self.temp_dir, file_name, f'temp_{file_name}')
        if r['status']:
            logging.info(f"✅ Файл переименован")
        else:
            logging.info(f"❌ произошла ошибка в обработке кадров: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        # Собираем новое видео
        r = images_to_video_with_audio_auto_fps('/'.join([self.temp_dir, f'{name}_translated_frames']),
                                                '/'.join([self.temp_dir, f'{name}_translated.wav']),
                                                '/'.join([self.temp_dir, file_name]),
                                                path.replace(file_name, f'temp_{file_name}'))
        if r['status']:
            logging.info(f"✅ Сборка видео завершена")
        else:
            logging.info(f"❌ произошла ошибка в сборке видео: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        clean_directory(self.temp_dir, [file_name, f'temp_{file_name}'])
        
        return {'status': True}
        