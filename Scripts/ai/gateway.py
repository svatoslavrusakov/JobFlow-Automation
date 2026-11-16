"""Прямой запрос к Gemini API без посредника и дополнительных библиотек."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai.result import RESULT_SCHEMA
from ai.settings import KEY_FILE, read_text


API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def response_text(data):
    """Берёт текст последнего ответа модели из завершённого запроса."""
    if not isinstance(data, dict) or data.get("status") != "completed":
        raise RuntimeError("Gemini API не завершил генерацию.")

    steps = data.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError("В ответе Gemini API нет шагов генерации.")
    for step in reversed(steps):
        if isinstance(step, dict) and step.get("type") == "model_output":
            parts = step.get("content", [])
            if not isinstance(parts, list):
                break
            text = "".join(
                part["text"] for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
            if text.strip():
                return text
            break
    raise RuntimeError("Gemini API не вернул текст результата.")


def generate(prompt, settings, schema=None):
    """Отправляет запрос к модели из настроек и возвращает её JSON-текст."""
    if settings["provider"] != "gemini":
        raise RuntimeError("Сейчас поддерживается только provider gemini.")
    # Ключ хранится в локальном файле, который исключён из Git.
    key = read_text(settings.get("key_file", KEY_FILE))

    # Резюме остаётся в теле запроса; ключ передаём только в заголовке.
    payload = {
        "model": settings["model"],
        "input": prompt,
        "store": False,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            # Прежний вызов без schema по-прежнему запрашивает письмо.
            "schema": RESULT_SCHEMA if schema is None else schema,
        },
    }
    request = Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.get("timeout", 60)) as response:
            data = json.load(response)
    except HTTPError as error:
        # Тело ошибки не печатаем: в нём могут оказаться данные запроса.
        raise RuntimeError(f"Gemini API вернул HTTP {error.code}.") from None
    except URLError:
        raise RuntimeError("Не удалось подключиться к Gemini API.") from None
    except ValueError:
        raise RuntimeError("Gemini API вернул некорректный ответ.") from None
    return response_text(data)
