import os
from pydub import AudioSegment

def ensure_wav_format(input_path):
    # Если файл не в формате WAV, перекодируем его
    if not input_path.lower().endswith('.wav'):
        wav_path = os.path.splitext(input_path)[0] + '_temp.wav'
        command = f'ffmpeg -i "{input_path}" -vn -acodec pcm_s16le -ar 44100 -ac 2 "{wav_path}"'
        result = os.system(command)
        if result != 0:
            raise RuntimeError("Не удалось перекодировать файл в WAV")
        return wav_path
    else:
        return input_path

def wav_to_mp3(wav_file_path, mp3_file_path, bitrate="192k"):
    try:
        # Проверяем и при необходимости перекодируем
        wav_path = ensure_wav_format(wav_file_path)
        audio = AudioSegment.from_file(wav_path, format="wav")
        audio.export(mp3_file_path, format="mp3", bitrate=bitrate)
        print(f"Преобразование завершено: {mp3_file_path}")
        # Удаляем временный файл, если он создан
        if wav_path != wav_file_path:
            os.remove(wav_path)
    except Exception as e:
        print(f"Ошибка при преобразовании: {e}")