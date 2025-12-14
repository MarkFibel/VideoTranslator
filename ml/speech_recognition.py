import whisper
from .utils.utils import Response
class SimpleWhisper:
    """
    Простой класс для инициализации модели Whisper и распознавания аудио.
    Использует локальную библиотеку `whisper`.
    """

    def __init__(self, model_name: str = "small", device: str = "cpu"):
        if model_name not in whisper.available_models():
            raise ValueError(f"Model '{model_name}' is not available. Choose from: {whisper.available_models()}")
        self.model = whisper.load_model(model_name, device=device)

    def transcribe(self, audio_path: str) -> str:
        """Возвращает только распознанный текст."""
        try:
            result = self.model.transcribe(audio_path)
            text = result.get("text", "")
            return Response(True, None, text)
        except Exception as e:
            return Response(False, e, None)
    