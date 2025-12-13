import os
import json


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
