import os
import asyncio
import tempfile
from fastapi import FastAPI, Request
from telegram_logic import send_message_to_telegram
from zoom_logic import download_zoom_file, transcribe_audio
from text_logic import convert_to_plans_and_tasks

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok", "message": "Zoom to Telegram Bot is running"}


@app.get("/test")
def test():
    try:
        send_message_to_telegram("Тестовое сообщение с Railway 🚂")
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}


@app.post("/zoom/webhook")
async def zoom_webhook(request: Request):
    """
    Обрабатывает webhook от Zoom о завершении записи встречи.
    Ожидает событие 'recording.completed' с download_url.
    """
    try:
        data = await request.json()
        print("ZOOM WEBHOOK:", data)
        
        # Проверяем тип события
        event = data.get("event", "")
        
        if event != "recording.completed":
            print(f"Игнорируем событие: {event}")
            return {"status": "ignored", "event": event}
        
        # Извлекаем download_url из payload
        payload = data.get("payload", {})
        object_data = payload.get("object", {})
        recording_files = object_data.get("recording_files", [])
        
        if not recording_files:
            send_message_to_telegram("⚠️ Запись завершена, но файлы не найдены")
            return {"status": "no_files"}
        
        # Ищем аудио файл (MP3, M4A) или берем первый доступный
        recording_file = None
        for file in recording_files:
            file_type = file.get("file_type", "").lower()
            file_extension = file.get("file_extension", "").lower()
            if file_type == "audio" or file_extension in ["mp3", "m4a", "wav"]:
                recording_file = file
                break
        
        # Если аудио не найдено, берем первый файл (обычно это видео с аудио)
        if not recording_file:
            recording_file = recording_files[0]
        
        download_url = recording_file.get("download_url")
        
        if not download_url:
            send_message_to_telegram("⚠️ Запись завершена, но download_url отсутствует")
            return {"status": "no_download_url"}
        
        meeting_topic = object_data.get("topic", "Встреча")
        
        # Быстро отвечаем на webhook, чтобы избежать таймаута
        # Обработку запускаем в фоне
        asyncio.create_task(process_recording_async(download_url, recording_file, meeting_topic))
        
        return {"status": "accepted", "meeting": meeting_topic}
            
    except Exception as e:
        error_msg = f"❌ Ошибка обработки webhook: {str(e)}"
        print(error_msg)
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
        # Отправляем уведомление о начале обработки
        send_message_to_telegram(f"🎥 Обрабатываю запись: *{meeting_topic}*")
        
        # Скачиваем файл во временную директорию
        with tempfile.TemporaryDirectory() as temp_dir:
            file_extension = recording_file.get("file_extension", "mp4")
            file_path = os.path.join(temp_dir, f"recording.{file_extension}")
            
            # Скачиваем файл
            download_zoom_file(download_url, file_path)
            
            # Транскрибируем аудио
            send_message_to_telegram("🎤 Транскрибирую аудио...")
            transcription = transcribe_audio(file_path)
            
            # Преобразуем в формат "планы и задачи"
            send_message_to_telegram("📝 Форматирую в планы и задачи...")
            formatted_text = convert_to_plans_and_tasks(transcription)
            
            # Отправляем результат в Telegram
            final_message = f"📋 *Планы и задачи из встречи: {meeting_topic}*\n\n{formatted_text}"
            send_message_to_telegram(final_message)
            
    except Exception as e:
        error_msg = f"❌ Ошибка обработки записи: {str(e)}"
        print(error_msg)
        try:
            send_message_to_telegram(error_msg)
        except:
            pass
