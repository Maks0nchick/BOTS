# Инструкция по настройке Webhook в Zoom

## ⚠️ Важно: Webhook должен быть настроен в Zoom Marketplace!

## Пошаговая инструкция:

### 1. Создай приложение в Zoom Marketplace

1. Перейди на https://marketplace.zoom.us/
2. Войди в свой аккаунт Zoom
3. Нажми **"Develop"** → **"Build App"** (или **"Manage"** → **"Created Apps"**)
4. Выбери тип приложения: **"Server-to-Server OAuth"** или **"Webhook Only"**
5. Заполни информацию о приложении:
   - App name: любое имя (например, "Telegram Bot")
   - Company name: твое имя/компания
   - Developer contact: твой email
6. Нажми **"Create"**

### 2. Настрой Event Subscriptions (Webhook)

1. В настройках созданного приложения найди раздел **"Event Subscriptions"** или **"Webhook"**
2. Нажми **"Add Event Subscription"** или **"Add Webhook"**
3. Заполни:
   - **Subscription Name**: любое имя (например, "Recording Webhook")
   - **Event Notification Endpoint URL**: 
     ```
     https://bots-production-tg.up.railway.app/zoom/webhook
     ```
4. В разделе **"Event types"** или **"Subscribe to events"**:
   - Найди событие **"Recording has completed"** или **"recording.completed"**
   - **Включи его** (поставь галочку/переключатель)
5. Нажми **"Save"** или **"Add"**

### 3. Активируй приложение

1. После создания webhook, вернись на главную страницу приложения
2. Нажми кнопку **"Activate"** или переключи статус на **"Active"**
3. Zoom может запросить подтверждение - подтверди

### 4. Проверь настройки

После активации:
- Zoom может отправить тестовый GET запрос на `/zoom/webhook`
- В логах Railway должно появиться: `"GET запрос на /zoom/webhook - валидация webhook от Zoom"`
- Если видишь это сообщение - webhook настроен правильно!

### 5. Проверь после конференции

После завершения конференции с записью:
1. Подожди несколько минут (Zoom обрабатывает запись)
2. Проверь логи Railway
3. Должно появиться: `"POST запрос на /zoom/webhook получен"`
4. Если его нет - проверь:
   - Что запись действительно завершена в Zoom
   - Что событие `recording.completed` включено
   - Что приложение активировано

## Частые проблемы:

### ❌ Webhook не приходит
- **Проблема**: Webhook не настроен или не активирован
- **Решение**: Проверь шаги 1-3 выше

### ❌ GET запрос приходит, но POST нет
- **Проблема**: Событие `recording.completed` не включено
- **Решение**: Проверь настройки Event Subscriptions, убедись что событие включено

### ❌ Запись завершена, но webhook не приходит
- **Проблема**: Zoom еще обрабатывает запись
- **Решение**: Подожди 5-10 минут после завершения конференции

## Проверка через Zoom API (опционально):

Если у тебя есть доступ к Zoom API, можешь проверить статус webhook:
- Перейди в настройки приложения в Zoom Marketplace
- Проверь раздел "Event Subscriptions"
- Должен быть активный webhook с URL `https://bots-production-tg.up.railway.app/zoom/webhook`

