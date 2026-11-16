"""Сохраняет статус и дату проверки ответа; остальные ячейки не изменяет."""

from datetime import datetime

from gspread.utils import rowcol_to_a1

from tables import sheets
from core import utils


def update_response_row(
    sheet, row_number, original_row, vacancy_id, status, checked_at=None,
):
    """Обновляет статус и время проверки. True означает, что была запись."""
    if original_row["Статус"].strip() != "wait":
        raise ValueError("Проверять ответы можно только для строки со статусом wait.")

    original_id, _ = utils.parse_vacancy_link(original_row["Ссылка"])
    if original_id != vacancy_id or original_row["ID"].strip() not in ("", vacancy_id):
        raise ValueError("ID строки не соответствует проверенной вакансии.")
    if status not in ("wait", "reject", "invite", "archive", "unavailable"):
        raise ValueError("Получен неизвестный статус отклика.")

    if checked_at is None:
        # Исключение только для старых архивных отметок, без посещения hh.
        if status != "archive" or original_row.get("Доступность", "").strip() != "archive":
            raise ValueError("Для результата проверки нужно время её выполнения.")
    elif not isinstance(checked_at, datetime):
        raise ValueError("Время проверки должно быть объектом datetime.")

    headers = sheets.read_headers(sheet)
    if "Дата проверки" not in headers:
        raise ValueError("Добавьте колонку «Дата проверки» в выбранный лист.")

    # Даты нужны в том же отображаемом виде, что и при чтении очереди.
    current = sheets.read_current_row(
        sheet, row_number, headers,
        date_time_render_option="FORMATTED_STRING",
    )
    if current["Дата проверки"].lstrip().startswith("="):
        raise ValueError("В «Дата проверки» находится формула. Запись пропущена.")

    fields = ("ID", "Ссылка", "Статус", "Дата проверки")
    if "Доступность" in original_row:
        fields += ("Доступность",)
    for field in fields:
        if field not in current or field not in original_row:
            raise ValueError(f"Колонка «{field}» изменилась. Запись пропущена.")
        if current[field].strip() != original_row[field].strip():
            raise ValueError(f"Поле «{field}» изменилось. Запись пропущена.")

    wanted = {"Статус": status}
    if checked_at is not None:
        # ISO-порядок позволяет сортировать текстовые значения по времени.
        wanted["Дата проверки"] = checked_at.strftime("%Y-%m-%d %H:%M:%S")

    updates = [
        {
            "range": rowcol_to_a1(row_number, headers.index(field) + 1),
            "values": [[value]],
        }
        for field, value in wanted.items()
        if current[field].strip() != value
    ]
    if not updates:
        return False

    # Старую «Доступность» и прочие данные строки не изменяем.
    try:
        sheet.batch_update(updates, value_input_option="RAW")
    except KeyboardInterrupt:
        print("Обновление прервано. Проверьте результат в таблице.")
        raise
    return True
