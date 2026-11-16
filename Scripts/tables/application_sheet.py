# application_sheet.py

from gspread.utils import rowcol_to_a1

from tables import sheets
from core import utils
from core.row_queue import QUEUE_STATUSES, select_stage_rows
from core.run_options import RunOptions


# done отмечает завершённую обработку ИИ и сохранённое сопроводительное письмо.
SENDABLE_STATUSES = QUEUE_STATUSES["send"]


def require_ready_application(row):
    """Проверяет единое правило готовности строки к отправке."""
    if row.get("Статус", "").strip() not in SENDABLE_STATUSES:
        raise ValueError("Отправка разрешена только для статуса done.")
    if not row.get("Сопроводительное", "").strip():
        raise ValueError("У строки done отсутствует готовое сопроводительное письмо.")


def check_application_values(current, original_row):
    """Общая проверка снимка строки, без чтения Google и действий в браузере."""
    fields = ("ID", "Ссылка", "Статус", "Сопроводительное")
    for field in fields:
        if field not in current:
            raise ValueError(f"Нет поля «{field}».")
        if current[field].lstrip().startswith("="):
            raise ValueError(f"В «{field}» находится формула. Действие отменено.")
        if field == "Сопроводительное" and field not in original_row:
            continue
        if field not in original_row:
            raise ValueError(f"В исходном снимке нет поля «{field}».")
        before, after = original_row[field], current[field]
        if field != "Сопроводительное":
            before, after = before.strip(), after.strip()
        if after != before:
            raise ValueError(f"Поле «{field}» изменилось. Действие отменено.")
    require_ready_application(current)
    vacancy_id, _ = utils.parse_vacancy_link(current["Ссылка"])
    if current["ID"].strip() not in ("", vacancy_id):
        raise ValueError("ID строки не соответствует ссылке.")


def check_application_row(sheet, row_number, original_row):
    """Перечитывает строку; возвращает заголовки и актуальный снимок."""
    # Позиции колонок определяем заново: пользователь мог их переставить.
    headers = sheets.read_headers(sheet)
    fields = ("ID", "Ссылка", "Статус", "Сопроводительное")
    missing = [field for field in fields if field not in headers]
    if missing:
        raise ValueError("Не найдены колонки: " + ", ".join(missing))

    # Заголовки уже проверены; общее чтение сохраняет формулы и пустые ячейки.
    current = sheets.read_current_row(sheet, row_number, headers)
    check_application_values(current, original_row)
    return headers, current


def update_application_row(sheet, row_number, original_row, status, comment=None):
    """Обновляет статус и дополняет комментарий после обработки вакансии."""
    if status not in (
        "wait", "reject", "invite", "archive", "unavailable", "form",
    ):
        raise ValueError("Получен неизвестный статус.")
    if comment is not None and not isinstance(comment, str):
        raise ValueError("Комментарий должен быть строкой.")

    # Перед записью убеждаемся, что обрабатываем всё ещё ту же строку.
    headers, current = check_application_row(sheet, row_number, original_row)
    wanted = {"Статус": status}
    if comment:
        if "Комментарий" not in headers:
            raise ValueError("Добавьте колонку «Комментарий».")
        # Берём последнюю заметку пользователя, чтобы не затереть её ссылкой.
        previous = current["Комментарий"]
        if previous.lstrip().startswith("="):
            print(
                f"Строка {row_number}: в комментарии формула; "
                f"добавьте вручную: {comment}"
            )
        elif comment not in previous:
            separator = "\n" if previous and not previous.endswith("\n") else ""
            wanted["Комментарий"] = previous + separator + comment

    # Меняем только нужные ячейки статуса и комментария, а не всю строку.
    updates = [
        {
            "range": rowcol_to_a1(row_number, headers.index(field) + 1),
            "values": [[value]],
        }
        for field, value in wanted.items()
        if current[field] != value
    ]
    if updates:
        # RAW сохраняет текст без распознавания формул.
        # При ошибке останавливаем запуск. Перезапуск снова проверит hh.
        sheet.batch_update(updates, value_input_option="RAW")


def read_send_queue(sheet, options=None):
    """Проверяет колонки и выбирает готовые отклики из таблицы."""
    options = options or RunOptions()
    headers = sheets.read_headers(sheet)
    missing = [
        field for field in ("Сопроводительное", "Комментарий")
        if field not in headers
    ]
    if missing:
        raise ValueError("Добавьте колонки: " + ", ".join(missing))

    # Для всей таблицы читаем только ID, ссылку и статус.
    rows = sheets.read_vacancy_rows(sheet, headers=headers)
    # Пусто/new не отправляются; после сбоя done снова проверяется на hh.
    pending = select_stage_rows(rows, "send", options)
    return rows, pending
