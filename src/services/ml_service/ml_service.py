"""
Сервис перевода видео.
"""

import logging
from src.services.base_service import BaseService
from src.services.ml_service.ml_pipelines import get_ocr, get_spech_recognize, get_translate, get_tts
from src.services.ml_service.utils import split_video_to_frames, extract_audio_from_video, images_to_video_with_audio_auto_fps, tr_frames

logger = logging.getLogger(__name__)


class MLService(BaseService):
    """
    Сервис для обработки видео.
    """
    
    def __init__(self, temp_dir):
        self.translate = get_translate()
        self.spech_recognize = get_spech_recognize()
        self.ocr = get_ocr()
        self.tts = get_tts()
        
        self.temp_dir = temp_dir
    
    def execute(self, data: dict) -> dict:
        """
        Основной метод для обработки видео.
        """

        logger.info(f"MLService.execute called with data: {data}")
        
        # Получаем параметр message из входных данных
        message = data.get("message", "No message provided")
        
        # TODO: Здесь выызываем пайплайн обработки видео
        path = data.get("path", '')
        #TODO результат писать в тот же файл. Оригинал делаем с припиской temp
        result_dir = data.get("res_dir", 'var/results')
        if path == '':
            logging.info(f"Путь не распознан")
        # path = 'path/to/video'
        # result_dir = 'directory/for/done/video'
        
        r = self.__process_video(path, result_dir)
        
        # Формируем ответ
        result = {
            "status": "success",
            "message": f"Data received: {message}",
            "echo": data,
            "service": self.getName()
        }
        
        logger.info(f"MLService.execute returning: {result}")
        
        return result
    
    def __process_video(self, path: str, result_dir: str):
        #✅⚠️❌
        src_frames_dir = '/'.join([self.temp_dir, 'src_frames'])
        r = split_video_to_frames(path, src_frames_dir)
        logging.info(f"✅ Обработано кадров: {r['procced_frames']}")
        
        src_audio_dir = '/'.join([self.temp_dir, 'audio.mp3'])
        r = extract_audio_from_video(path, src_audio_dir)
        if r['status']:
            logging.info(f"✅ аудио успешно извлеченно")
        else:
            logging.info(f"❌ произошла ошибка в обработке аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
            
        r = self.spech_recognize(src_audio_dir)
        if r['status']:
            logging.info(f"✅ Получен текст из аудио, Текст: {r['text'][:100]}")
            text_from_audio = r['text']
        else:
            logging.info(f"❌ произошла ошибка в обработке аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        r = self.translate(text_from_audio)
        if r['status']:
            logging.info(f"✅ Текст переведен успешно, Текст: {r['text'][:100]}")
            translated_text_from_audio = r['text']
        else:
            logging.info(f"❌ произошла ошибка в переводе текста: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        translated_audio_dir = 'translated'
        r = self.tts(translated_text_from_audio, translated_audio_dir)
        if r['status']:
            logging.info(f"✅ Генерирование аудио завершено")
        else:
            logging.info(f"❌ произошла ошибка в генерации переведнного аудио: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        translated_frames_fir = '/'.join([self.temp_dir, 'translated_frames'])
        r = tr_frames(src_frames_dir, res_dir=translated_frames_fir) #TODO 
        if r['status']:
            logging.info(f"✅ Перевод фрэймов заверешен")
        else:
            logging.info(f"❌ произошла ошибка в переводе фреймов: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        r = images_to_video_with_audio_auto_fps('/'.join([self.temp_dir, 'translated_frames']),
                                                '/'.join([self.temp_dir, 'translated.wav']),
                                                '/'.join([result_dir, 'final_video.mp4']), #TODO записывать в оригинал
                                                path)
        if r['status']:
            logging.info(f"✅ Сборка видео завершена")
        else:
            logging.info(f"❌ произошла ошибка в сборке видео: {r['error']}")
            return {'status': False, 'error': r['error']}
        
        #TODO Удалять временные файлы
        
        return {'status': True}
        