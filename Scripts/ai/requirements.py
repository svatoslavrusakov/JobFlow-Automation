"""Извлекает ключевые слова через общий ИИ-шлюз и проверяет JSON."""

import json

from ai import gateway
from ai.result import InvalidAIResult

# Только явные соответствия: SQL и PostgreSQL, Java и JavaScript различаются.
ALIASES = {
    "python": "Python", "pyhton": "Python", "пайтон": "Python",
    "sql": "SQL", "postgresql": "PostgreSQL", "excel": "Excel",
    "git": "Git", "java": "Java", "javascript": "JavaScript",
    "c++": "C++", "c#": "C#", ".net": ".NET", "power bi": "Power BI",
}
KEYWORDS_SCHEMA = {
    "type": "object",
    "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
    "required": ["keywords"],
}


def parse_keywords(text):
    """Возвращает слова через ; без повторов; — означает корректный пустой результат."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        raise InvalidAIResult("Ключевые слова: нужен корректный JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("keywords"), list):
        raise InvalidAIResult("Ключевые слова: нужен список keywords.")
    names = []
    for name in data["keywords"]:
        if not isinstance(name, str) or not name.strip() or ";" in name:
            raise InvalidAIResult("Каждое ключевое слово должно быть непустой строкой без ;.")
        key = " ".join(name.split()).casefold()
        names.append(ALIASES.get(key, key))
    # dict сохраняет порядок; явный маркер позволяет пропустить пустой ответ при перезапуске.
    result = "; ".join(dict.fromkeys(names)) or "—"
    if len(result) > 45000:
        raise InvalidAIResult("Ключевые слова не помещаются в одну ячейку Google.")
    return result


def analyze(description, options, template):
    """Одна вакансия — один запрос без резюме и истории предыдущих вакансий."""
    prompt = template.replace("{{description}}", description)
    answer = gateway.generate(prompt, options, schema=KEYWORDS_SCHEMA)
    return parse_keywords(answer)
