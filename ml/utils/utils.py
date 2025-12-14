import os
import json
from typing import Any

def extract_name(path):
    basename = os.path.basename(path)
    filename = os.path.splitext(basename)[0]
    return filename

def unique_indices(data):
    seen = set()
    unique_idxs = []

    for i, item in enumerate(data):
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique_idxs.append(i)
    
    return unique_idxs

def fill_with_unique(data):
    seen = set()
    lst = []
    for i, item in enumerate(data):
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            lst.append(i)
        else:
            lst.append(lst[-1])
    
    return lst
    
def get_image_paths(frames_dir):
    return [
        os.path.join(frames_dir, img)
        for img in os.listdir(frames_dir)
        if img.endswith(".jpg")
    ]

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def translate_ocr_results(translator, data):
    # карта уникальных страниц (длина == data)
    try:
        unique_map = fill_with_unique(data)
        unique_idxs = sorted(set(unique_map))

        texts = []
        for idx in unique_idxs:
            for item in data[idx]:
                texts.append(item["text"])

        # 2. Переводим
        translations = translator.batch_translate(texts)

        # 3. Назначаем переводы уникальным страницам
        t_idx = 0
        for idx in unique_idxs:
            for item in data[idx]:
                item["translation"] = translations[t_idx]
                t_idx += 1

        # 4. Копируем текст в дубликаты
        for i, page in enumerate(data):
            original_idx = unique_map[i]
            for item, orig_item in zip(page, data[original_idx]):
                item["translation"] = orig_item["translation"]
        return Response(True, None, data)
    except Exception as e:
        return Response(False, e, None)



class Response:
    def __init__(self, status: bool, error: str|None, result: Any):
        self.status = status
        self.error = error
        self.result = result
