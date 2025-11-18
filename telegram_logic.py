import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Максимальная длина сообщения в Telegram (4096 символов)
MAX_MESSAGE_LENGTH = 4096

def send_message_to_telegram(text: str):
    """Отправляет текстовое сообщение в Telegram группу"""
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID должны быть установлены")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Если сообщение слишком длинное, разбиваем на части
    if len(text) > MAX_MESSAGE_LENGTH:
        # Разбиваем по абзацам, стараясь не разрывать структуру
        parts = []
        current_part = ""
        
        for line in text.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH - 100:
                if current_part:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    # Если одна строка слишком длинная, обрезаем
                    parts.append(line[:MAX_MESSAGE_LENGTH - 100] + '...')
                    current_part = ''
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part)
        
        # Отправляем все части
        results = []
        for i, part in enumerate(parts, 1):
            if len(parts) > 1:
                part = f"*Часть {i}/{len(parts)}*\n\n{part}"
            payload = {"chat_id": CHAT_ID, "text": part, "parse_mode": "Markdown"}
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            results.append(resp.json())
        
        return results
    else:
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
