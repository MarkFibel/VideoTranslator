import cv2
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from PIL import ImageFont
import os
from .utils import Response

def get_font(font_path=None, font_size=20):
    """
    Возвращает объект шрифта PIL с поддержкой русского языка.
    Если font_path не указан, использует стандартные пути для MacOS, Linux, Windows.
    """
    possible_paths = []

    if font_path:
        possible_paths.append(font_path)
    
    # Пути по умолчанию для MacOS
    possible_paths += [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/DejaVuSans.ttf"
    ]
    # Пути по умолчанию для Linux
    possible_paths += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    # Пути по умолчанию для Windows
    possible_paths += [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, font_size)

    raise OSError("Не найден шрифт для русского текста. Укажите font_path с .ttf файлом")

def draw_translations_on_image(image_path, annotations, output_path, font_path=None):
    """
    Закрашивает текст на изображении и добавляет русский перевод.

    Args:
        image_path (str): путь к исходному изображению
        annotations (list): список словарей с 'bbox' и 'translation'
        output_path (str): путь для сохранения результата
        font_path (str, optional): путь к .ttf шрифту с поддержкой кириллицы
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size


    for ann in annotations:
        bbox = ann["bbox"]

        translation = ann.get('translation', ann['text'])

        x1 = int(bbox[0] * img_width)
        y1 = int(bbox[1] * img_height)
        x2 = int(bbox[2] * img_width)
        y2 = int(bbox[3] * img_height)

        draw.rectangle([x1, y1, x2, y2], fill="white")

        # Подбор размера шрифта
        font_size = 10
        font = get_font(font_path=font_path, font_size=font_size)
        while True:
            bbox_text = draw.textbbox((0, 0), translation, font=font)
            text_width = bbox_text[2] - bbox_text[0]
            text_height = bbox_text[3] - bbox_text[1]
            if text_width >= (x2 - x1) or text_height >= (y2 - y1):
                font_size -= 1
                font = get_font(font_path=font_path, font_size=font_size)
                break
            font_size += 1
            font = get_font(font_path=font_path, font_size=font_size)

        # Рисуем текст
        draw.text((x1, y1), translation, fill="black", font=font)

    img.save(output_path)

def translate_images(images, all_annotations, output_dir, font_path="arial.ttf"):
    """
    Обрабатывает список изображений и аннотаций, добавляя русский текст поверх.

    Args:
        images (list): список путей к исходным изображениям
        all_annotations (list): список списков аннотаций для каждого изображения
        output_dir (str): папка для сохранения обработанных изображений
        font_path (str): путь к .ttf шрифту, поддерживающему русский язык
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        for img_path, annotations in zip(images, all_annotations):
            # Имя файла для сохранения
            filename = os.path.basename(img_path)
            output_path = os.path.join(output_dir, filename)

            # Вызываем функцию для одного изображения
            draw_translations_on_image(img_path, annotations, output_path, font_path=font_path)
        return Response(True, None, None)
    except Exception as e:
        return Response(False, e, None)


