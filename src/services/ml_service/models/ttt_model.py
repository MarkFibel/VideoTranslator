# Model for text translation

import logging
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseTranslationModel:
    def __init__(self):
        pass
    
    def __call__(self, text: str):
        return {'status': True, 'error': 'Error description', 'text': 'some text', 'source_text': text}

class OpusTextTranslationModel(BaseTranslationModel):
    def __init__(self):
        super().__init__()
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-ru", cache_dir='./model_cache')
            self.model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-en-ru", cache_dir='./model_cache')
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
