from doctr.io import DocumentFile, Document
from doctr.models import ocr_predictor
import torch
import json
from tqdm import tqdm
from .utils.utils import Response

class OCR:
    def __init__(self, device: str = None):
        self.device = device or ('mps' if torch.backends.mps.is_available() else 'cpu')
        self.model = ocr_predictor(pretrained=True).to(self.device)
        self.model.eval()  # отключаем обучение

    def __call__(self, document):
        return self.model(document)
    
    def process(self, image_path: str):
        """Обработка одного изображения в документ."""
        try:
            doc = DocumentFile.from_images(image_path)
            return Response(True, None, doc)
        except Exception as e:
            return Response(False, e, None)
    
    def batch(self, image_paths: list[str]):
        """Обработка нескольких изображений с отображением прогресса."""
        try:
            results = []
            for img_path in tqdm(image_paths, desc="Processing images"):
                doc = DocumentFile.from_images(img_path)
                result = self.model(doc)
                results.append(result)
            return Response(True, None, results)
        except Exception as e:
            return Response(False, e, None)
    
    def save_results_to_json(self, results, output_path):
        """Сохраняет результаты OCR в JSON с прогресс-баром по страницам."""
        try:
            data = []
            for result in tqdm(results, desc="Saving OCR results"):
                for page in result.pages:
                    page_data = []
                    for block in page.blocks:
                        for line in block.lines:
                            line_text = ' '.join([word.value for word in line.words])
                            bbox = line.geometry
                            (x_min, y_min), (x_max, y_max) = bbox
                            bbox = [x_min, y_min, x_max, y_max]
                            line_info = {
                                'text': line_text,
                                'bbox': bbox
                            }
                            page_data.append(line_info)
                    data.append(page_data)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            return Response(True, None, None)
        except Exception as e:
            return Response(False, e, None)
