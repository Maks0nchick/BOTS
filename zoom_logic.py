import os
import requests
import whisper

# Инициализация модели Whisper (загружается один раз)
_model = None

def get_whisper_model():
    """Ленивая загрузка модели Whisper"""
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model

def download_zoom_file(download_url: str, save_path: str):
    """Скачивает файл записи Zoom по download_url (с access_token)"""
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()

    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            if chunk:
                f.write(chunk)

    return save_path

def transcribe_audio(audio_path: str) -> str:
    """Транскрибирует аудио файл в текст используя Whisper"""
    model = get_whisper_model()
    result = model.transcribe(audio_path, language="ru")
    return result["text"]
