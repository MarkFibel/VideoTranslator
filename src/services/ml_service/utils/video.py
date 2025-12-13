import cv2
import os
from .utils import Response
# try:
#     from moviepy.editor import ImageSequenceClip, AudioFileClip, VideoFileClip, VideoClip
# except ImportError:
#     print("moviepy is not installed. Audio extraction will not work.")
try:
    from moviepy import ImageSequenceClip, AudioFileClip, VideoFileClip
except ImportError:
    print("moviepy is not installed. Audio extraction will not work.")


def extract_frames(path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        # Попытка открыть снова без указания backend
        cap = cv2.VideoCapture( path)
        if not cap.isOpened():
            return Response(False,'Не удалось открыть видеофайл', None)
    # Успешное открытие видео
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imwrite(os.path.join(output_dir, f"frame_{frame_count:08d}.jpg"),
                    frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        frame_count += 1
    cap.release()
    return Response(True, None, frame_count)

def extract_audio(video_path, output_audio_path):
    """
    Извлекает аудио из видео и сохраняет в файл.

    :param video_path: путь к видеофайлу
    :param output_audio_path: путь для сохранения аудиофайла
    """
    try:
        with VideoFileClip(video_path) as video:
            audio = video.audio
            audio.write_audiofile(output_audio_path)
        return Response(True, None, None)
    except Exception as e:
        return Response(False, e, None)
        

def create_video_with_new_audio(images_dir, original_video_path, new_audio_path, output_video_path):
    """
    Создает новое видео из изображений и нового аудио.
    """
    try:
        image_files = sorted([
            os.path.join(images_dir, f)
            for f in os.listdir(images_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ])
        if not image_files:
            raise ValueError("В указанной папке нет изображений")

        with VideoFileClip(original_video_path) as orig_video, AudioFileClip(new_audio_path) as audio_clip:
            video_size = orig_video.size
            audio_duration = audio_clip.duration
            frame_duration = audio_duration / len(image_files)
            video_clip = ImageSequenceClip(image_files, durations=[frame_duration]*len(image_files))
            video_clip = video_clip.resized(new_size=video_size)
            video_clip = video_clip.with_audio(audio_clip)
            video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
        return Response(True, None, None)
    except Exception as e:
        return Response(False, None, None)