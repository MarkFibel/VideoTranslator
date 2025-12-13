from transformers import VitsModel, AutoTokenizer
import torch
import scipy.io.wavfile as wavfile

class TextToSpeech:
    def __init__(self, model_name="facebook/mms-tts-rus", device=None):
        """
        Инициализация модели TTS и токенизатора.
        
        Args:
            model_name (str): название предобученной модели.
            device (str, optional): устройство для работы модели ('cpu' или 'cuda'). 
                                     Если None, автоматически выбирается CUDA если доступна.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = VitsModel.from_pretrained(model_name).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.sampling_rate = self.model.config.sampling_rate

    def synthesize(self, text, output_path="output.wav"):
        """
        Синтезирует аудио из текста и сохраняет его в файл.
        
        Args:
            text (str): текст для синтеза.
            output_path (str): путь для сохранения WAV-файла.
        """
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            waveform = self.model(**inputs).waveform

        # Преобразуем тензор в numpy и сохраняем в WAV
        waveform_np = waveform.squeeze().cpu().numpy()
        wavfile.write(output_path, rate=self.sampling_rate, data=waveform_np)
        print(f"Audio saved to {output_path}")

# Пример использования
if __name__ == "__main__":
    tts = TextToSpeech()
    tts.synthesize("Пример текста на русском языке", output_path="techno.wav")
