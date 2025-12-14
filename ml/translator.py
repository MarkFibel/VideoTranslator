from transformers import FSMTForConditionalGeneration, FSMTTokenizer
import torch
from tqdm import tqdm
from .utils.utils import Response


class Translator:
    def __init__(self, model_name="facebook/wmt19-en-ru", device=None):
        print('Initializing Translator...')
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = FSMTTokenizer.from_pretrained(model_name)
        self.model = FSMTForConditionalGeneration.from_pretrained(model_name).to(self.device)
        self.model.eval()  # отключаем режим обучения

        total_params = sum(p.numel() for p in self.model.parameters())
        print(f"Total model parameters: {total_params}")


    def translate(self, text: str) -> str:
        with torch.no_grad():  # отключаем вычисление градиентов
            input_ids = self.tokenizer.encode(text, return_tensors="pt").to(self.device)
            outputs = self.model.generate(input_ids)
            return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def batch_translate(self, texts: list, max_length: int = 512, batch_size: int = 16) -> list:
        """
        Батчевая генерация с tqdm и разбивкой на подбатчи для экономии памяти.
        """
        translations = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Translating batches"):
            batch_texts = texts[i:i + batch_size]
            with torch.no_grad():
                encoded = self.tokenizer(
                    batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=max_length
                ).to(self.device)
                outputs = self.model.generate(**encoded)
                translations.extend([self.tokenizer.decode(t, skip_special_tokens=True) for t in outputs])
        return translations


import torch
from tqdm import tqdm
from transformers import (
    FSMTForConditionalGeneration, FSMTTokenizer,
    MarianMTModel, MarianTokenizer,
    T5ForConditionalGeneration, T5Tokenizer
)


import torch
from tqdm import tqdm
from transformers import (
    FSMTForConditionalGeneration, FSMTTokenizer,
    MarianMTModel, MarianTokenizer,
    T5ForConditionalGeneration, T5Tokenizer,
    AutoTokenizer, AutoModelForCausalLM
)


class UniversalTranslator:
    """
    Универсальный переводчик, поддерживающий:

    - facebook/wmt19-en-ru (FSMT)
    - rinkorn/marian-finetuned-opus100-en-to-ru (MarianMT)
    - utrobinmv/t5_translate_en_ru_zh_small_1024 (T5)
    - NiuTrans/LMT-60-8B (Causal LM chat model)
    """

    def __init__(self, model_name: str, device: str = None, model_type: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name

        # -----------------------------------------
        # Auto-detection of model type
        # -----------------------------------------
        if model_type is not None:
            self.model_type = model_type
        if "wmt19" in model_name or model_type == 'fsmt':
            self.model_type = "fsmt"
            self.tokenizer = FSMTTokenizer.from_pretrained(model_name)
            self.model = FSMTForConditionalGeneration.from_pretrained(model_name)

        elif "marian" in model_name or "opus100" in model_name or model_type == 'marian':
            self.model_type = "marian"
            self.tokenizer = MarianTokenizer.from_pretrained(model_name)
            self.model = MarianMTModel.from_pretrained(model_name)

        elif "t5" in model_name or model_type == 't5':
            self.model_type = "t5"
            self.tokenizer = T5Tokenizer.from_pretrained(model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(model_name)

        elif "LMT-60" in model_name or "NiuTrans" in model_name or model_type == 'chatlm':
            # NEW: support for NiuTrans/LMT-60-8B
            self.model_type = "chatlm"
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                padding_side="left"
            )
            self.model = AutoModelForCausalLM.from_pretrained(model_name)

        else:
            raise ValueError(f"Unsupported model: {model_name}")

        # Move model to device
        self.model.to(self.device)
        self.model.eval()

    def translate(self, text: str, max_new_tokens: int = 256) -> str:
        with torch.no_grad():
            if self.model_type == "t5":
                try:
                    encoded = self.tokenizer(
                        text, return_tensors="pt", padding=True, truncation=True
                    ).to(self.device)

                    output = self.model.generate(
                        encoded.input_ids,
                        max_new_tokens=max_new_tokens
                    )

                    text = self.tokenizer.decode(output[0], skip_special_tokens=True)
                    return Response(True, None, text)
                except Exception as e:
                    return Response(False, e, None)

            # ------------------------------
            # FSMT / Marian
            # ------------------------------
            try:
                encoded = self.tokenizer(
                    text, return_tensors="pt"
                ).to(self.device)

                output = self.model.generate(
                    **encoded,
                    max_new_tokens=max_new_tokens
                )

                text = self.tokenizer.decode(output[0], skip_special_tokens=True)
                return Response(True, None, text)
            except Exception as e:
                return Response(False, e, None)

    # =======================================================================
    #               BATCH TRANSLATION
    # =======================================================================

    def batch_translate(self, texts: list, batch_size: int = 8, max_new_tokens: int = 256):
        results = []

        # -----------------------------------------------------
        # LMT-60-8B: batch mode via chat template
        # -----------------------------------------------------
        if self.model_type == "chatlm":
            try:
                for i in tqdm(range(0, len(texts), batch_size), desc="Translating batches"):
                    batch = texts[i:i + batch_size]

                    messages_batch = []
                    for txt in batch:
                        prompt = (
                            "Translate the following text from English into Chinese.\n"
                            f"English: {txt}\n"
                            "Chinese:"
                        )
                        messages_batch.append(
                            self.tokenizer.apply_chat_template(
                                [{"role": "user", "content": prompt}],
                                tokenize=False,
                                add_generation_prompt=True
                            )
                        )

                    encoded = self.tokenizer(
                        messages_batch,
                        return_tensors="pt",
                        padding=True,
                        truncation=True
                    ).to(self.device)

                    generated = self.model.generate(
                        **encoded,
                        max_new_tokens=max_new_tokens,
                        num_beams=5,
                        do_sample=False
                    )

                    # remove prompts
                    for j, output_ids in enumerate(generated):
                        prompt_len = len(encoded.input_ids[j])
                        ans_ids = output_ids[prompt_len:]
                        results.append(
                            self.tokenizer.decode(ans_ids, skip_special_tokens=True)
                        )


                return Response(True, None, results)
            except Exception as e:
                return Response(False, e, None)

        # -----------------------------------------------------
        # Other models: FSMT / Marian / T5
        # -----------------------------------------------------
        try:
            for i in tqdm(range(0, len(texts), batch_size), desc="Translating batches"):
                batch = texts[i:i + batch_size]

                with torch.no_grad():
                    encoded = self.tokenizer(
                        batch, return_tensors="pt", padding=True, truncation=True
                    ).to(self.device)

                    outputs = self.model.generate(
                        **encoded,
                        max_new_tokens=max_new_tokens
                    )

                    decoded = [
                        self.tokenizer.decode(t, skip_special_tokens=True)
                        for t in outputs
                    ]

                results.extend(decoded)

            return Response(True, None, results)
        except Exception as e:
            return Response(False, e, None)


from time import perf_counter
import json
def test_universal_translator(transcript_output_dir, translator: UniversalTranslator):
    start_time = perf_counter()
    with open(transcript_output_dir, 'r', encoding='utf-8') as f:
        data = json.load(f)

        all_texts = []
        for page in data:
            for item in page:
                source_text = item['text']
                # translation = self.translator.translate(source_text)
                # item['translation'] = translation
                all_texts.append(source_text)
        translations = translator.batch_translate(all_texts, batch_size=32)
        # idx = 0
        # for page in data:
        #     for item in page:
        #         item['translation'] = translations[idx]
        #         idx += 1
        end_time = perf_counter()
        # print(f"⌛Функция Translator.batch_translate завершена | Время выполнения: {end_time - start_time:.4f} сек")

        return end_time - start_time

if __name__ == "__main__":
    # Пример использования
    tr_fsm = UniversalTranslator("facebook/wmt19-en-ru", device='mps')
    print(tr_fsm.translate("Hello world"))
    tr_marian = UniversalTranslator("glazzova/translation_en_ru", device='mps', model_type='marian')
    print(tr_marian.translate("Hello world"))
    # tr_t5 = UniversalTranslator("utrobinmv/t5_translate_en_ru_zh_small_1024", device='mps')
    # print(tr_t5.translate("Hello world"))
    tr_chatlm = UniversalTranslator("NiuTrans/LMT-60-0.6B-Base", device='mps')
    print(tr_chatlm.translate("Hello world"))

    transcript_output_dir = "var/tmp/test.vi.deo/ocr_transcript.json"
    # tr_t5_time = test_universal_translator(transcript_output_dir, tr_t5) 
    # tr_fsm_time = test_universal_translator(transcript_output_dir, tr_fsm)
    
    tr_marian_time = test_universal_translator(transcript_output_dir, tr_marian)
    
    # 
    # print(f"FSMT time: {tr_fsm_time:.4f} sec", f"Total parameters: {tr_fsm.total_params:,}")
    
    print(f"MarianMT glazzova/translation_en_ru time: {tr_marian_time:.4f} sec", f"Total parameters: {tr_marian.total_params:,}")
    # print(f"T5 time: {tr_t5_time:.4f} sec", f"Total parameters: {tr_t5.total_params:,}")


    # FSMT time: 143.4698 sec Total parameters: 293,195,776
    # MarianMT glazzova/translation_en_ru time: 63.0334 sec Total parameters: 76,672,000