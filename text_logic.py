import os
from openai import OpenAI

# Инициализация OpenAI клиента
_openai_client = None

def get_openai_client():
    """Ленивая инициализация OpenAI клиента"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def convert_to_plans_and_tasks(transcription: str) -> str:
    """
    Преобразует транскрипцию встречи в формат "планы и задачи"
    """
    client = get_openai_client()
    
    if not client:
        # Если нет API ключа, возвращаем простую обработку
        return f"📋 Планы и задачи из встречи:\n\n{transcription}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Ты помощник, который преобразует транскрипцию встречи в структурированный формат 'Планы и задачи'. Выдели основные планы и конкретные задачи из текста. Форматируй ответ четко и структурированно."
                },
                {
                    "role": "user",
                    "content": f"Преобразуй следующую транскрипцию встречи в формат 'Планы и задачи':\n\n{transcription}"
                }
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        # Если ошибка с OpenAI, возвращаем транскрипцию с базовым форматированием
        return f"📋 Планы и задачи из встречи:\n\n{transcription}\n\n(Ошибка обработки через AI: {str(e)})"
