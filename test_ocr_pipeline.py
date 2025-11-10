import os
from src.services.ml_service.utils import split_video_to_frames
from src.services.ml_service.ml_pipelines import get_translate
from src.services.ml_service.models.itt_model import EasyOCRModel

if __name__ == '__main__':
    name = '' # TODO название видео
    path = '' # TODO путь к видео
    temp_dir = 'var/tmp'
    os.makedirs(temp_dir)
    
    # --- Разбиение видео на кадры ---
    src_frames_dir = os.path.join(temp_dir, f'{name}_src_frames')
    r = split_video_to_frames(path, src_frames_dir)
    
    translator = get_translate()
    ocr = EasyOCRModel(translator)
    
    r = ocr(name, src_frames_dir)
    print(r['results_dir'])
    