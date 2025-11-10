# from moviepy.editor import VideoFileClip
import moviepy as mp
print(mp.__file__)


def extract_audio(video_path: str, output_audio_path: str) -> None:
    # Загружаем видео файл
    with mp.VideoFileClip(video_path) as video:
        # Извлекаем аудио
        audio = video.audio
        # Сохраняем аудио в указанный файл
        audio.write_audiofile(output_audio_path)
        
def get_audio_name(path: str):
    name = path.replace('.mp4', '.mp3')
    return name

def get_translated_audio_name(path: str):
    name = path.replace(path.split('/')[-1], 'translated_' + path.split('/')[-1])
    return name
    
if __name__ == '__main__':
    path = 'data/sample.mp4'
    a = get_audio_name(path)
    print(a)