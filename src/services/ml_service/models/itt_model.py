# Model for OCR
from src.config.services.ml_config import settings
from src.services.ml_service.ml_pipelines import get_translate
import os
import matplotlib.pyplot as plt
import cv2
import easyocr
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
# # Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

class BaseTranslationModel:
    def __init__(self):
        pass
    
    def __call__(self, text: str):
        return {'status': True, 'error': 'Error description', 'text': 'some text', 'source_text': text}

class OpusTextTranslationModel(BaseTranslationModel):
    def __init__(self, cache_dir=settings.MODEL_CAHCE_DIR):
        super().__init__()
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-ru", cache_dir=cache_dir)
            self.model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-en-ru", cache_dir=cache_dir)
            logger.info("Model and tokenizer loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model/tokenizer: {e}")
            raise e

    def __call__(self, text: str):
        if not text.strip():
            return {'status': False, 'error': 'Empty input text', 'source_text': text}

        try:
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            if inputs["input_ids"].size(1) == 0:
                return {'status': False, 'error': 'No tokens produced by tokenizer', 'source_text': text}

            logger.info(f"Tokenized input shape: {inputs['input_ids'].shape}")

            import torch
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(device)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            outputs = self.model.generate(**inputs)
            translated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return {'status': True, 'text': translated_text, 'source_text': text}

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return {'status': False, 'error': str(e), 'source_text': text}

def get_text_size(font, text):
    # Используем getbbox для получения размеров текста
    bbox = font.getbbox(text)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width, height

def get_max_font_size(text, font_path, max_width, max_height):
    font_size = 1
    while True:
        font = ImageFont.truetype(font_path, font_size)
        # Получаем размеры текста
        text_width, text_height = get_text_size(font, text)
        if text_width > max_width or text_height > max_height:
            break
        font_size += 1
    return font_size - 1  # Возвращаем последний подходящий размер

def process_(img_path, results, translator, save_path):
    img1 = cv2.imread(img_path)
    pil_img = Image.fromarray(cv2.cvtColor(img1.copy(), cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    font_size = 32
    font = ImageFont.truetype(font_path, font_size)
    color = (0, 127, 255)
    fill_color = (255, 255, 255)
    for result in results:
        box, text, prob = result
        left_up, right_up, right_down, left_down = box
        
        r = translator(text)
        if r['status']:
            rect_top_left = left_up
            rect_bottom_right = right_down
            rect_width = rect_bottom_right[0] - rect_top_left[0]
            rect_height = rect_bottom_right[1] - rect_top_left[1]
            translated_text = r['text']
            # Получаем максимальный размер шрифта для текста в прямоугольнике
            font_size = get_max_font_size(translated_text, font_path, rect_width, rect_height)
            font = ImageFont.truetype(font_path, font_size)

            # Получаем размеры текста для центрирования
            text_width, text_height = get_text_size(font, translated_text)

            # Вычисляем позицию для центрирования текста внутри прямоугольника
            text_x = rect_top_left[0] + (rect_width - text_width) / 2
            text_y = rect_top_left[1] + (rect_height - text_height) / 2

            # Рисуем прямоугольник
            draw.rectangle([rect_top_left, rect_bottom_right], outline="black", fill="lightgray")

            # Рисуем текст
            draw.text((text_x, text_y), translated_text, font=font, fill="black")


class BaseOCRModel:
    def __init__(self, translator):
        self.translator = translator
    
    def __call__(self, folder_path: str, destination_path: str):
        return {'status': True, 'error': 'Error description',}
    
class EasyOCRModel(BaseOCRModel):
    def __init__(self, translator, temp_dir=settings.TEMP_DIR):
        self.translator = translator
        self.temp_dir = temp_dir
        self.reader = easyocr.Reader(['en'], gpu=False) # this needs to run only once to load the model into memory
        self.workers = 4
        
               
    def __call__(self, name: str, source_dir: str):
        destination_dir = '/'.join([self.temp_dir, f'{name}_translated'])
        paths = ['/'.join([source_dir, file_name]) for file_name in os.listdir(source_dir)]
        results_images = self.reader.readtext_batched(paths, workers=self.workers)
        
        for (source_img_path, results) in zip(paths, results_images):
            save_path = '/'.join([destination_dir, os.path.basename(source_img_path)])
            process_(source_img_path, results, self.translator, save_path)
        return {'status': True, 'result_dir': f'{name}_translated'}

def main():
    translator = get_translate()
    ocr = EasyOCRModel(translator)
    name = 'pupupu'
    source_dir = 'var/data/frames_output'
    
    r = ocr(name, source_dir)
    print(r['results_dir'])
    
