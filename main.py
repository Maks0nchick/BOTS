import os
import asyncio
import tempfile
import logging
import hmac
import hashlib
from collections import deque
from fastapi import FastAPI, Request
from telegram_logic import send_message_to_telegram, send_file_to_telegram
from zoom_logic import download_zoom_file, transcribe_audio
from text_logic import convert_to_plans_and_tasks

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ZOOM_WEBHOOK_SECRET_TOKEN = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN", "")
# Храним последние обработанные встречи, чтобы избежать повторной обработки
PROCESSED_MEETINGS = set()
PROCESSED_QUEUE = deque(maxlen=200)


def mark_meeting_processed(meeting_uuid: str):
    if not meeting_uuid:
        return
    if meeting_uuid not in PROCESSED_MEETINGS:
        PROCESSED_MEETINGS.add(meeting_uuid)
        PROCESSED_QUEUE.append(meeting_uuid)
        # Если превысили лимит — удаляем самый старый
        while len(PROCESSED_MEETINGS) > PROCESSED_QUEUE.maxlen:
            old = PROCESSED_QUEUE.popleft()
            PROCESSED_MEETINGS.discard(old)


def is_meeting_processed(meeting_uuid: str) -> bool:
    return meeting_uuid in PROCESSED_MEETINGS


def unmark_meeting_processed(meeting_uuid: str):
    if not meeting_uuid:
        return
    PROCESSED_MEETINGS.discard(meeting_uuid)
    try:
        PROCESSED_QUEUE.remove(meeting_uuid)
    except ValueError:
        pass

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok", "message": "Zoom to Telegram Bot is running"}


@app.get("/test")
def test():
    """Тестовая отправка сообщения в Telegram"""
    try:
        send_message_to_telegram("Тестовое сообщение с Railway 🚂")
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}


@app.post("/zoom/webhook/test")
async def test_webhook(request: Request):
    """Тестовый endpoint для проверки webhook - принимает любой POST и логирует"""
    try:
        body = await request.body()
        logger.info("=" * 50)
        logger.info("ТЕСТОВЫЙ WEBHOOK получен")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Body: {body.decode('utf-8', errors='ignore')}")
        
        try:
            data = await request.json()
            logger.info(f"Parsed JSON: {data}")
        except:
            pass
            
        return {"status": "received", "message": "Test webhook received"}
    except Exception as e:
        logger.error(f"Ошибка в тестовом webhook: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/zoom/webhook")
async def zoom_webhook_get(request: Request):
    """
    Обрабатывает GET запрос от Zoom для валидации webhook (challenge-response)
    Zoom отправляет GET запрос с параметром 'plainToken' и ожидает его в ответе
    """
    logger.info("=" * 50)
    logger.info("GET запрос на /zoom/webhook - валидация webhook от Zoom")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query params: {dict(request.query_params)}")
    
    # Zoom отправляет challenge-токен для валидации
    plain_token = request.query_params.get("plainToken")
    
    if plain_token:
        logger.info(f"Получен challenge token: {plain_token}")
        response = {"plainToken": plain_token}

        if ZOOM_WEBHOOK_SECRET_TOKEN:
            encrypted_token = hmac.new(
                ZOOM_WEBHOOK_SECRET_TOKEN.encode(),
                plain_token.encode(),
                hashlib.sha256,
            ).hexdigest()
            response["encryptedToken"] = encrypted_token
        else:
            logger.warning("ZOOM_WEBHOOK_SECRET_TOKEN не установлен — validation может не пройти")

        return response
    else:
        # Если токена нет, возвращаем обычный ответ
        logger.info("Challenge token не найден, возвращаю обычный ответ")
        return {"status": "ok", "message": "Webhook endpoint is active"}


@app.get("/zoom/webhook/status")
async def webhook_status():
    """
    Проверка статуса webhook endpoint
    """
    return {
        "status": "active",
        "endpoint": "/zoom/webhook",
        "methods": ["GET", "POST"],
        "message": "Webhook готов принимать запросы от Zoom"
    }


@app.post("/zoom/webhook")
async def zoom_webhook(request: Request):
    """
    Обрабатывает webhook от Zoom о завершении записи встречи.
    Ожидает событие 'recording.completed' с download_url.
    """
    try:
        # Логируем все входящие запросы
        logger.info("=" * 50)
        logger.info("POST запрос на /zoom/webhook получен")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Пробуем получить данные
        try:
            data = await request.json()
            logger.info(f"Webhook data: {data}")
        except Exception as json_error:
            # Если не JSON, пробуем получить как текст
            body = await request.body()
            logger.error(f"Ошибка парсинга JSON: {json_error}")
            logger.error(f"Raw body: {body.decode('utf-8', errors='ignore')}")
            return {"status": "error", "error": "Invalid JSON"}
        
        # Проверяем тип события
        event = data.get("event", "")
        logger.info(f"Тип события: {event}")
        
        # Обработка валидации URL от Zoom (challenge-response)
        if event == "endpoint.url_validation":
            payload = data.get("payload", {})
            plain_token = payload.get("plainToken")
            if plain_token:
                logger.info(f"Валидация URL: получен plainToken: {plain_token}")
                response = {"plainToken": plain_token}

                if ZOOM_WEBHOOK_SECRET_TOKEN:
                    encrypted_token = hmac.new(
                        ZOOM_WEBHOOK_SECRET_TOKEN.encode(),
                        plain_token.encode(),
                        hashlib.sha256,
                    ).hexdigest()
                    response["encryptedToken"] = encrypted_token
                else:
                    logger.warning(
                        "ZOOM_WEBHOOK_SECRET_TOKEN не установлен — validation может не пройти"
                    )
                return response
            else:
                logger.warning("Валидация URL: plainToken не найден в payload")
                return {"status": "error", "error": "plainToken not found"}
        
        if event != "recording.completed":
            logger.info(f"Игнорируем событие: {event}")
            # Отправляем уведомление о других событиях для отладки
            try:
                send_message_to_telegram(f"📥 Получено событие от Zoom: {event}")
            except:
                pass
            return {"status": "ignored", "event": event}
        
        # Извлекаем download_url из payload
        payload = data.get("payload", {})
        logger.info(f"Payload: {payload}")
        
        object_data = payload.get("object", {})
        meeting_uuid = object_data.get("uuid")
        if meeting_uuid and is_meeting_processed(meeting_uuid):
            logger.info(f"Встреча {meeting_uuid} уже обработана — пропускаю повторный webhook")
            return {"status": "duplicate", "meeting": meeting_uuid}
        recording_files = object_data.get("recording_files", [])
        
        logger.info(f"Найдено файлов записи: {len(recording_files)}")
        
        if not recording_files:
            error_msg = "⚠️ Запись завершена, но файлы не найдены"
            logger.warning(error_msg)
            send_message_to_telegram(error_msg)
            return {"status": "no_files"}
        
        audio_file = None
        video_file = None
        for file in recording_files:
            file_type = file.get("file_type", "").lower()
            file_extension = file.get("file_extension", "").lower()
            logger.info(f"Файл: type={file_type}, ext={file_extension}")
            if not audio_file and (file_type == "audio" or file_extension in ["mp3", "m4a", "wav"]):
                audio_file = file
            if not video_file and (file_type in ["shared_screen_with_speaker_view", "video"] or file_extension in ["mp4", "mov", "mkv"]):
                video_file = file
        
        if not audio_file:
            audio_file = recording_files[0]
        if not video_file:
            video_file = audio_file
        
        meeting_topic = object_data.get("topic", "Встреча")
        download_token = data.get("download_token")
        logger.info(f"Тема встречи: {meeting_topic}")
        
        logger.info("Запускаю асинхронную обработку записи...")
        mark_meeting_processed(meeting_uuid)
        asyncio.create_task(
            process_recording_async(
                audio_file, video_file, meeting_topic, download_token, meeting_uuid
            )
        )
        
        logger.info("Webhook обработан успешно")
        return {"status": "accepted", "meeting": meeting_topic}
            
    except Exception as e:
        error_msg = f"❌ Ошибка обработки webhook: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            send_message_to_telegram(error_msg)
        except:
            pass
        return {"status": "error", "error": str(e)}


async def process_recording_async(
    audio_recording: dict,
    video_recording: dict,
    meeting_topic: str,
    download_token: str | None = None,
    meeting_uuid: str | None = None,
):
    """
    Асинхронная обработка записи: скачивание, транскрипция и отправка в Telegram
    """
    try:
        logger.info(f"Начало обработки записи: {meeting_topic}")
        # Отправляем уведомление о начале обработки
        send_message_to_telegram(f"🎥 Обрабатываю запись: *{meeting_topic}*")
        
        # Скачиваем файл во временную директорию
        with tempfile.TemporaryDirectory() as temp_dir:
            video_extension = video_recording.get("file_extension", "mp4")
            video_path = os.path.join(temp_dir, f"recording_video.{video_extension}")
            download_zoom_file(
                video_recording.get("download_url"),
                video_path,
                access_token=download_token,
            )
            send_message_to_telegram(f"📹 Отправляю запись встречи: *{meeting_topic}*")
            send_file_to_telegram(video_path, caption=f"🎥 Запись встречи: {meeting_topic}")
            
            audio_extension = audio_recording.get("file_extension", video_extension)
            audio_path = video_path
            if audio_recording.get("id") != video_recording.get("id") or audio_extension.lower() != video_extension.lower():
                audio_path = os.path.join(temp_dir, f"recording_audio.{audio_extension}")
                download_zoom_file(
                    audio_recording.get("download_url"),
                    audio_path,
                    access_token=download_token,
                )
            
            send_message_to_telegram("🎤 Транскрибирую аудио...")
            transcription = transcribe_audio(audio_path)
            
            # Сохраняем транскрипт в файл
            transcript_path = os.path.join(temp_dir, "transcript.txt")
            with open(transcript_path, "w", encoding="utf-8") as transcript_file:
                transcript_file.write(transcription.strip())
            send_file_to_telegram(
                transcript_path, caption=f"🗒️ Полная транскрибация: {meeting_topic}"
            )
            
            # Преобразуем в формат "планы и задачи"
            send_message_to_telegram("📝 Форматирую в планы и задачи...")
            formatted_text = convert_to_plans_and_tasks(transcription)
            
            final_message = f"📋 *Планы и задачи из встречи: {meeting_topic}*\n\n{formatted_text}"
            send_message_to_telegram(final_message)
            
    except Exception as e:
        error_msg = f"❌ Ошибка обработки записи: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            send_message_to_telegram(error_msg)
        except:
            pass
        unmark_meeting_processed(meeting_uuid or "")
