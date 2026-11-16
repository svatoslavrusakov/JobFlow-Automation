"""Экспорт одного публичного канала → обычные HTML-снимки без обращения к сети."""

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


def normalize_channel(url):
    """Имя канала задаёт пользователь: в экспорте есть ID, но нет публичного адреса."""
    address = urlsplit(url.strip())
    match = re.fullmatch(r"/(?:s/)?([A-Za-z][A-Za-z0-9_]*)/?", address.path)
    if (address.scheme != "https" or address.netloc != "t.me" or not match
            or address.query or address.fragment
            or match[1].lower() in ("c", "s", "joinchat", "share", "proxy", "login", "iv")):
        raise ValueError("Укажите адрес публичного канала: https://t.me/channel_name.")
    return "https://t.me/" + match[1].lower()


def read_export(path):
    """Принимает result.json одного канала; общий архив аккаунта не разбирает."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("type") != "public_channel":
        raise ValueError("Нужен JSON-экспорт одного публичного канала, не всего аккаунта.")
    if not isinstance(data.get("messages"), list) or not isinstance(data.get("name"), str):
        raise ValueError("В экспорте нужны название канала и список messages.")
    return data["name"], data["messages"]


def read_text(value):
    """Собирает строки и форматированные части; скрытые ссылки сохраняет рядом с текстом."""
    parts = [value] if isinstance(value, str) else value
    if not isinstance(parts, list):
        raise ValueError("Текст сообщения должен быть строкой или списком частей.")
    result = []
    for part in parts:
        if isinstance(part, str):
            result.append(part)
            continue
        if not isinstance(part, dict) or not isinstance(part.get("text"), str):
            raise ValueError("Повреждён текст сообщения.")
        result.append(part["text"])
        if part.get("type") == "text_link":
            if not isinstance(part.get("href"), str):
                raise ValueError("У скрытой ссылки отсутствует строка href.")
            result.append(" (" + part["href"] + ")")
    return "".join(result)


def render_message(message, channel_name):
    """Служебные записи и пустые вложения пропускает; чужой текст не становится разметкой."""
    if not isinstance(message, dict):
        raise ValueError("Сообщение должно быть объектом JSON.")
    if message.get("type") == "service":
        return None
    if message.get("type") != "message" or type(message.get("id")) is not int or message["id"] < 1:
        raise ValueError("Нужны тип message и положительный целый ID сообщения.")
    text = read_text(message.get("text"))
    if not text.strip():
        return None
    # Только текст поста и подпись источника: медиа и служебные данные не копируем.
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><body>'
            f'<header>Канал Telegram: {escape(channel_name)}</header>'
            f'<article><pre>{escape(text)}</pre></article></body></html>')
