"""Формат черновика резюме и проверка ссылок на исходный текст."""

import json

from ai.result import InvalidAIResult

SECTION_TITLES = ("О себе", "Навыки", "Опыт работы", "Образование", "Контакты", "Дополнительно")
RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "enum": list(SECTION_TITLES)},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "source_quotes": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["text", "source_quotes"],
                        },
                    },
                },
                "required": ["title", "items"],
            },
        },
        "changes": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sections", "changes", "questions"],
}


def read_strings(value, field, allow_empty=True):
    """Проверяет список пояснений, вопросов или цитат."""
    if not isinstance(value, list) or (not allow_empty and not value):
        raise InvalidAIResult(f"Резюме: «{field}» должен быть списком нужной длины.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise InvalidAIResult(f"Резюме: в «{field}» нужен непустой текст.")
    return [item.strip() for item in value]


def parse_resume(text, original):
    """Пропускает только известные поля и цитаты, найденные в исходном резюме."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise InvalidAIResult("Резюме: модель вернула некорректный JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list) or not data["sections"]:
        raise InvalidAIResult("Резюме: нужен непустой список sections.")
    source = " ".join(original.split())
    sections, seen = [], set()
    for section in data["sections"]:
        if not isinstance(section, dict):
            raise InvalidAIResult("Резюме: раздел должен быть объектом.")
        title, items = section.get("title"), section.get("items")
        if title not in SECTION_TITLES or title in seen:
            raise InvalidAIResult("Резюме: неизвестный или повторный заголовок раздела.")
        if not isinstance(items, list) or not items:
            raise InvalidAIResult("Резюме: раздел должен содержать items.")
        checked = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
                raise InvalidAIResult("Резюме: у пункта нет текста.")
            quotes = read_strings(item.get("source_quotes"), "source_quotes", allow_empty=False)
            if any(" ".join(quote.split()) not in source for quote in quotes):
                raise InvalidAIResult("Резюме: цитата не найдена в исходном файле.")
            checked.append({"text": item["text"].strip(), "source_quotes": quotes})
        sections.append({"title": title, "items": checked})
        seen.add(title)
    # Наличие цитаты не доказывает смысловую точность переписанного пункта.
    # Человек проверяет формулировки и полноту; модель не может одобрить свой результат.
    return {
        "sections": sections,
        "changes": read_strings(data.get("changes"), "changes"),
        "questions": read_strings(data.get("questions"), "questions"),
    }
