# sheet.py

from gspread.utils import rowcol_to_a1

from tables import sheets
from core import utils


AI_COLUMNS = (
    "Сопроводительное", "Подводные камни", "Оценка ИИ", "Требования к отклику",
)
AI_HEADERS = sheets.REQUIRED_HEADERS + AI_COLUMNS
SOURCE_FIELDS = (
    "ID", "Ссылка", "Статус", "Заголовок",
    "Компания", "Зарплата", "Описание",
)
WATCHED_FIELDS = SOURCE_FIELDS + AI_COLUMNS


def require_empty_results(row):
    """Одна проверка готовых результатов для генератора и предпросмотра."""
    for field in AI_COLUMNS:
        if row[field].lstrip().startswith("="):
            raise ValueError(f"В поле «{field}» находится формула.")
    if any(row[field].strip() for field in AI_COLUMNS):
        raise ValueError("В строке уже есть результат ИИ или ручной текст.")


def read_row(sheet, row_number, queued):
    """Проверяет строку перед платным запросом к модели."""
    headers = sheets.read_headers(sheet, required_headers=AI_HEADERS)
    current = sheets.read_current_row(sheet, row_number, headers)

    # Перед вызовом API проверяем, что строка всё ещё относится к этой вакансии.
    for field in ("ID", "Ссылка", "Статус"):
        if current[field].strip() != queued[field].strip():
            raise ValueError(f"Поле «{field}» изменилось после чтения очереди.")
    if current["Статус"].strip() != "new":
        raise ValueError("ИИ обрабатывает только строки со статусом new.")
    if not current["Заголовок"].strip() or not current["Описание"].strip():
        raise ValueError("У строки нет заголовка или описания.")

    # Формулы и ручные результаты не заменяем ответом модели.
    for field in SOURCE_FIELDS:
        if current[field].lstrip().startswith("="):
            raise ValueError(f"В поле «{field}» находится формула.")
    require_empty_results(current)

    # Сейчас ИИ-этап принимает только ссылки hh.
    vacancy_id, _ = utils.parse_vacancy_link(current["Ссылка"])
    if current["ID"].strip() not in ("", vacancy_id):
        raise ValueError("ID строки не совпадает со ссылкой.")
    return current


def build_result_values(result):
    """Готовит результаты ИИ и причину ручной проверки."""
    checks = result["application_checks"]
    return {
        "Сопроводительное": result["cover_letter"],
        "Подводные камни": "\n".join(
            f"• {item['issue']} — {item['reason']}" for item in result["pitfalls"]
        ),
        "Оценка ИИ": result["fit_score"],
        "Требования к отклику": "\n".join(
            f"• {item['requirement']}\n  Цитата: «{item['quote']}»" for item in checks
        ),
        # Любое специальное требование проверяет пользователь, даже если оно выполнено.
        "Статус": "thinking" if checks else "done",
    }


def save_result(sheet, row_number, before, result):
    """Сохраняет результаты и статус одним запросом, возвращает статус."""
    headers = sheets.read_headers(sheet, required_headers=AI_HEADERS)
    current = sheets.read_current_row(sheet, row_number, headers)
    # Сверяем исходные поля после генерации, чтобы не затереть новые правки.
    for field in WATCHED_FIELDS:
        if current[field] != before[field]:
            raise ValueError(f"Поле «{field}» изменилось во время генерации.")
    if current["Статус"].strip() != "new":
        raise ValueError("Статус изменился во время генерации.")

    values = build_result_values(result)
    # Адреса колонок берём из заголовков: порядок колонок не важен.
    updates = [
        {
            "range": rowcol_to_a1(row_number, headers.index(field) + 1),
            "values": [[value]],
        }
        for field, value in values.items()
    ]
    # RAW не превращает письмо или пояснения в формулы.
    sheet.batch_update(updates, value_input_option="RAW")
    return values["Статус"]
