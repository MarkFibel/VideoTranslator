import whisper

class SimpleWhisper:
    """
    Простой класс для инициализации модели Whisper и распознавания аудио.
    Использует локальную библиотеку `whisper`.
    """

    def __init__(self, model_name: str = "small", device: str = "cpu"):
        print('Initializing SimpleWhisper...')
        print(f'Loading model: {model_name} on device: {device}')
        print(f'Available models: {whisper.available_models()}')
        if model_name not in whisper.available_models():
            raise ValueError(f"Model '{model_name}' is not available. Choose from: {whisper.available_models()}")
        self.model = whisper.load_model(model_name, device=device)

        # Логирование количества параметров
        total_params = sum(p.numel() for p in self.model.parameters())
        print(f"Total parameters: {total_params:,}")

    def transcribe(self, audio_path: str) -> str:
        """Возвращает только распознанный текст."""
        result = self.model.transcribe(audio_path)
        return result.get("text", "")
    