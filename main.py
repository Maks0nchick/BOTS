import os
import asyncio
import tempfile
import logging
import hmac
import hashlib
from fastapi import FastAPI, Request
from telegram_logic import send_message_to_telegram, send_file_to_telegram
from zoom_logic import download_zoom_file, transcribe_audio
from text_logic import convert_to_plans_and_tasks

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ZOOM_WEBHOOK_SECRET_TOKEN = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN", "")

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
        recording_files = object_data.get("recording_files", [])
        
        logger.info(f"Найдено файлов записи: {len(recording_files)}")
        
        if not recording_files:
            error_msg = "⚠️ Запись завершена, но файлы не найдены"
            logger.warning(error_msg)
            send_message_to_telegram(error_msg)
            return {"status": "no_files"}
        
        # Ищем аудио файл (MP3, M4A) или берем первый доступный
        recording_file = None
        for file in recording_files:
            file_type = file.get("file_type", "").lower()
            file_extension = file.get("file_extension", "").lower()
            logger.info(f"Файл: type={file_type}, ext={file_extension}")
            if file_type == "audio" or file_extension in ["mp3", "m4a", "wav"]:
                recording_file = file
                break
        
        # Если аудио не найдено, берем первый файл (обычно это видео с аудио)
        if not recording_file:
            recording_file = recording_files[0]
        
        download_url = recording_file.get("download_url")
        logger.info(f"Download URL: {download_url[:100] if download_url else 'None'}...")
        
        if not download_url:
            error_msg = "⚠️ Запись завершена, но download_url отсутствует"
            logger.warning(error_msg)
            send_message_to_telegram(error_msg)
            return {"status": "no_download_url"}
        
        meeting_topic = object_data.get("topic", "Встреча")
        logger.info(f"Тема встречи: {meeting_topic}")
        
        # Быстро отвечаем на webhook, чтобы избежать таймаута
        # Обработку запускаем в фоне
        logger.info("Запускаю асинхронную обработку записи...")
        asyncio.create_task(process_recording_async(download_url, recording_file, meeting_topic))
        
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


async def process_recording_async(download_url: str, recording_file: dict, meeting_topic: str):
    """
    Асинхронная обработка записи: скачивание, транскрипция и отправка в Telegram
    """
    try:
        logger.info(f"Начало обработки записи: {meeting_topic}")
        # Отправляем уведомление о начале обработки
        send_message_to_telegram(f"🎥 Обрабатываю запись: *{meeting_topic}*")
        
        # Скачиваем файл во временную директорию
        with tempfile.TemporaryDirectory() as temp_dir:
            file_extension = recording_file.get("file_extension", "mp4")
            file_path = os.path.join(temp_dir, f"recording.{file_extension}")
            
            # Скачиваем файл
            download_zoom_file(download_url, file_path)
            
            # Отправляем файл записи в Telegram
            send_message_to_telegram(f"📹 Отправляю запись встречи: *{meeting_topic}*")
            send_file_to_telegram(file_path, caption=f"🎥 Запись встречи: {meeting_topic}")
            
            # Транскрибируем аудио
            send_message_to_telegram("🎤 Транскрибирую аудио...")
            transcription = transcribe_audio(file_path)
            
            # Преобразуем в формат "планы и задачи"
            send_message_to_telegram("📝 Форматирую в планы и задачи...")
            formatted_text = convert_to_plans_and_tasks(transcription)
            
            # Отправляем результат в формате "планы и задачи" в Telegram
            final_message = f"📋 *Планы и задачи из встречи: {meeting_topic}*\n\n{formatted_text}"
            send_message_to_telegram(final_message)
            
    except Exception as e:
        error_msg = f"❌ Ошибка обработки записи: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            send_message_to_telegram(error_msg)
        except:
            pass
