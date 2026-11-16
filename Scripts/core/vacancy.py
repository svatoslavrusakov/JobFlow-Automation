"""Общий формат прочитанной вакансии: одинаковые поля для hh и внешних сайтов."""

from urllib.parse import urlsplit

VACANCY_FIELDS = (
    "ID", "Компания", "Компания ссылка", "Заголовок", "Зарплата", "Описание", "Ссылка",
)
OPTIONAL_FIELDS = ("Контакты hr", "Комментарий")


def normalize_vacancy(values):
    """Проверяет плоский словарь; неизвестные данные остаются пустыми строками."""
    if not isinstance(values, dict) or set(values) - set(VACANCY_FIELDS + OPTIONAL_FIELDS):
        raise ValueError("Получены неизвестные поля вакансии.")
    if any(field not in values for field in VACANCY_FIELDS):
        raise ValueError("Отсутствуют основные поля вакансии.")
    if any(not isinstance(value, str) for value in values.values()):
        raise ValueError("Поля вакансии должны быть строками.")
    vacancy = {field: value.strip() for field, value in values.items()}
    if any(not vacancy[field] for field in ("ID", "Заголовок", "Описание", "Ссылка")):
        raise ValueError("У вакансии нет ID, названия, описания или ссылки.")
    if any(len(value) > 45000 for value in vacancy.values()):
        raise ValueError("Поле вакансии слишком длинное для одной ячейки таблицы.")
    for field in ("Ссылка", "Компания ссылка"):
        if vacancy[field]:
            parts = urlsplit(vacancy[field])
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError(f"В поле «{field}» нужна полная ссылка http:// или https://.")
    # Не добавляем пустые необязательные колонки в существующий сценарий hh.
    return {field: vacancy[field] for field in VACANCY_FIELDS + OPTIONAL_FIELDS
            if field in VACANCY_FIELDS or vacancy.get(field)}
