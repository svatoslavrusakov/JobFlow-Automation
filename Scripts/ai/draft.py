# draft.py

import re

from ai import gateway, result


def build_prompt(vacancy, resume, template):
    """Собирает запрос из уже прочитанной вакансии и резюме."""
    description = vacancy.get("Описание", "").strip()
    if not description:
        raise ValueError("У вакансии нет описания для ИИ.")
    if not resume.strip():
        raise ValueError("Резюме для ИИ пустое.")

    # Эти поля вакансии и резюме будут переданы внешнему API.
    vacancy_text = "\n".join((
        f"Заголовок: {vacancy.get('Заголовок', '')}",
        f"Компания: {vacancy.get('Компания', '')}",
        f"Зарплата: {vacancy.get('Зарплата', '')}",
        f"Описание:\n{description}",
    ))
    # Один проход не подставляет маркеры, случайно попавшие в сами данные.
    values = {"{{vacancy}}": vacancy_text, "{{resume}}": resume}
    return re.sub(r"\{\{(?:vacancy|resume)\}\}", lambda match: values[match.group()], template)


def create_draft(vacancy, resume, settings, template):
    """Возвращает проверенный результат независимо от источника вакансии."""
    prompt = build_prompt(vacancy, resume, template)
    answer = gateway.generate(prompt, settings)
    # В таблицу попадёт только ответ с ожидаемой структурой JSON.
    return result.parse_result(answer, vacancy["Описание"])
