# Zoom to Telegram Bot

Бот для автоматической обработки записей Zoom встреч и отправки результатов в Telegram группу в формате "Планы и задачи".

## Функционал

1. ✅ Получает webhook от Zoom о завершении записи встречи
2. ✅ Скачивает запись по `download_url` (без необходимости OAuth токена)
3. ✅ Транскрибирует аудио в текст используя Whisper
4. ✅ Преобразует транскрипцию в формат "Планы и задачи" через OpenAI
5. ✅ Отправляет результат в Telegram группу

## Требования

- Python 3.8+
- FFmpeg (для обработки аудио/видео)
- Zoom аккаунт с включенными облачными записями
- Telegram Bot Token
- OpenAI API Key (опционально, для улучшенной обработки текста)

## Настройка Zoom

1. Включи опцию **"Загружать облачные записи"** (Allow downloads)
2. Включи общий доступ **"зрители могут просматривать запись"**
3. Настрой webhook в Zoom Marketplace:
   - Событие: `recording.completed`
   - Endpoint URL: `https://your-railway-app.railway.app/zoom/webhook`

## Переменные окружения

Установи следующие переменные в Railway:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
OPENAI_API_KEY=your_openai_api_key  # Опционально
PORT=8000  # Автоматически устанавливается Railway
```

### Как получить TELEGRAM_CHAT_ID:

1. Создай бота через [@BotFather](https://t.me/BotFather)
2. Добавь бота в группу
3. Отправь сообщение в группу
4. Перейди по ссылке: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Найди `chat.id` в ответе (для группы будет отрицательное число)

## Деплой на Railway

1. Подключи репозиторий к Railway
2. Railway автоматически определит Python проект (используется `nixpacks.toml` для установки FFmpeg)
3. Установи переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `OPENAI_API_KEY` (опционально)
4. Railway автоматически установит зависимости и запустит приложение

**Примечание:** FFmpeg устанавливается автоматически через `nixpacks.toml` для обработки аудио/видео файлов.

## Структура проекта

```
.
├── main.py              # FastAPI приложение с webhook endpoint
├── telegram_logic.py    # Логика отправки в Telegram
├── zoom_logic.py        # Скачивание и транскрипция записей
├── text_logic.py        # Преобразование текста в "Планы и задачи"
├── requirements.txt     # Python зависимости
└── Procfile            # Конфигурация для Railway
```

## API Endpoints

- `GET /` - Проверка статуса
- `GET /test` - Тестовая отправка сообщения в Telegram
- `POST /zoom/webhook` - Webhook endpoint для Zoom

## Примечания

- Whisper модель "base" загружается при первом использовании (~150MB)
- Обработка может занять время в зависимости от длины записи
- Если `OPENAI_API_KEY` не установлен, используется простое форматирование транскрипции
