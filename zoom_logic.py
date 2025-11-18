import os
import requests
import whisper
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Инициализация модели Whisper (загружается один раз)
_model = None


def get_whisper_model():
    """Ленивая загрузка модели Whisper"""
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def _append_access_token(download_url: str, access_token: str | None) -> str:
    if not access_token:
        return download_url

    parsed = urlparse(download_url)
    query = parse_qs(parsed.query)
    query["access_token"] = [access_token]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def download_zoom_file(download_url: str, save_path: str, access_token: str | None = None):
    """Скачивает файл записи Zoom по download_url, используя access_token при необходимости"""
    url_with_token = _append_access_token(download_url, access_token)
    resp = requests.get(url_with_token, stream=True)
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
