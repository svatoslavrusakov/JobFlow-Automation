# result.py

import json


# Эту же структуру запрашиваем у API; parse_result ниже проверяет значения сам.
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_letter": {"type": "string"},
        "application_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["requirement", "quote"],
            },
        },
        "pitfalls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["issue", "reason"],
            },
        },
        "fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["cover_letter", "pitfalls", "fit_score", "application_checks"],
}


class InvalidAIResult(ValueError):
    """Ответ модели не соответствует ожидаемому JSON."""


def parse_application_checks(items, description):
    """Проверяет требования и наличие цитат в описании вакансии."""
    if not isinstance(items, list):
        raise InvalidAIResult("application_checks должен быть списком.")

    source = " ".join(description.split())
    checked = []
    for item in items:
        if not isinstance(item, dict):
            raise InvalidAIResult("Требование должно быть объектом.")
        requirement, quote = item.get("requirement"), item.get("quote")
        if not all(isinstance(value, str) and value.strip() for value in (requirement, quote)):
            raise InvalidAIResult("У требования нет текста или цитаты.")
        if " ".join(quote.split()) not in source:
            raise InvalidAIResult("Цитата требования не найдена в вакансии.")
        checked.append({"requirement": requirement.strip(), "quote": quote.strip()})
    return checked


def parse_result(text, description):
    """Проверяет ответ модели и оставляет только согласованные поля."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise InvalidAIResult("Модель вернула не JSON.") from error
    if not isinstance(data, dict):
        raise InvalidAIResult("Ответ ИИ должен быть объектом JSON.")

    letter = data.get("cover_letter")
    score = data.get("fit_score")
    pitfalls = data.get("pitfalls")
    if not isinstance(letter, str) or not letter.strip():
        raise InvalidAIResult("В ответе ИИ нет сопроводительного письма.")
    # bool в Python является int, поэтому проверяем точный тип оценки.
    if type(score) is not int or not 0 <= score <= 100:
        raise InvalidAIResult("fit_score должен быть целым числом от 0 до 100.")
    if not isinstance(pitfalls, list):
        raise InvalidAIResult("pitfalls должен быть списком.")

    checked_pitfalls = []
    for item in pitfalls:
        if not isinstance(item, dict):
            raise InvalidAIResult("Каждый подводный камень должен быть объектом.")
        issue = item.get("issue")
        reason = item.get("reason")
        if not isinstance(issue, str) or not issue.strip():
            raise InvalidAIResult("У подводного камня отсутствует issue.")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidAIResult("У подводного камня отсутствует reason.")
        checked_pitfalls.append({
            "issue": issue.strip(),
            "reason": reason.strip(),
        })

    return {
        "cover_letter": letter.strip(),
        "pitfalls": checked_pitfalls,
        "fit_score": score,
        "application_checks": parse_application_checks(
            data.get("application_checks"), description,
        ),
    }
