"""Распознаёт сохранённую страницу через существующий ИИ-шлюз."""

import json
import re
from urllib.parse import urljoin

from ai import gateway
from ai.result import InvalidAIResult
from core.vacancy import OPTIONAL_FIELDS, VACANCY_FIELDS, normalize_vacancy

# Адрес и ID назначает программа; модель возвращает только содержание страницы.
EXTRACT_FIELDS = tuple(field for field in VACANCY_FIELDS if field not in ("ID", "Ссылка")) + OPTIONAL_FIELDS
VACANCY_SCHEMA = {
    "type": "object",
    "properties": {field: {"type": "string"} for field in EXTRACT_FIELDS},
    "required": list(EXTRACT_FIELDS),
}


def parse_vacancy(text, source):
    """Проверяет ответ и приводит его к тому же формату, что возвращает hh."""
    try:
        values = json.loads(text)
    except (TypeError, ValueError):
        raise InvalidAIResult("Распознавание HTML: нужен корректный JSON.") from None
    if not isinstance(values, dict) or set(values) != set(EXTRACT_FIELDS):
        raise InvalidAIResult("Распознавание HTML: набор полей не соответствует схеме.")
    if any(not isinstance(value, str) for value in values.values()):
        raise InvalidAIResult("Распознавание HTML: поля должны быть строками.")
    if values["Компания ссылка"].strip():
        values["Компания ссылка"] = urljoin(source["final_url"], values["Компания ссылка"].strip())
    # Для внешних сайтов сохраняем весь исходный адрес, включая параметры и #.
    values.update({"ID": "site:" + source["key"], "Ссылка": source["source_url"]})
    try:
        return normalize_vacancy(values)
    except ValueError as error:
        raise InvalidAIResult(str(error)) from None


def extract_vacancy(html, source, options, template):
    """Одна страница — один запрос без резюме и истории других вакансий."""
    replacements = {"{{html}}": html, "{{url}}": source["final_url"]}
    # Один проход не заменяет маркеры, случайно встретившиеся внутри самой страницы.
    prompt = re.sub(r"\{\{(?:html|url)\}\}", lambda match: replacements[match.group()], template)
    answer = gateway.generate(prompt, options, schema=VACANCY_SCHEMA)
    return parse_vacancy(answer, source)
