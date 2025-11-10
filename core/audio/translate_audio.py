
import os
from ..utils import extract_audio, get_audio_name, get_translated_audio_name
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS


class AudioTranslate:
    def __init__(self, text_translater):
        self.text_translator = text_translater
    
    def _audio_to_text(self, path: str):
        # Загружаем предобученную модель
        model = whisper.load_model("base")  # варианты: tiny, base, small, medium, large
        # Распознаем речь
        result = model.transcribe(path, language="ru")
        return result
    
    def _text_to_audio(self, text: str, path: str):
        # Создаем TTS-объект
        tts = gTTS(text=text, lang="ru")

        # Сохраняем результат в аудиофайл
        translated_audio_path = get_translated_audio_name(path)
        tts.save(translated_audio_path)
    
    def translate(self, path: str):
        self.__translate(path)
            
    def __translate(self, path: str):
        audio_path = get_audio_name(path)
        extract_audio(path, audio_path)
        
        result = self._audio_to_text(audio_path)
        
        text = result["text"]

        translated = GoogleTranslator(source="en", target="ru").translate(text)
        
        self._text_to_audio(translated, path)

        

if __name__ == '__main__':
    trans = AudioTranslate()
    trans.translate('data/sample.mp4')
        
        

        
        
        
        
        
        
        
    
        