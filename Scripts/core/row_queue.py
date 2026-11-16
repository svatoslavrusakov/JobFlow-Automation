# row_queue.py

from datetime import datetime

from core import stop_control


def select_link_rows(rows, statuses=("",), start_row=2):
    """Выбирает строки со ссылкой и разрешённым статусом."""
    # По умолчанию статус пустой; None разрешает любой статус для извлечения ключевых слов.
    # Исходные номера строк сохраняем для последующих проверок и записи.
    return [
        (number, row)
        for number, row in rows
        if number >= start_row
        and row["Ссылка"].strip() and (statuses is None or row["Статус"].strip() in statuses)
    ]


def limit_rows(rows, limit):
    """Ограничивает выбранные строки; None сохраняет всю очередь."""
    return rows if limit is None else rows[:limit]


def filter_check_dates(rows, checked_from=None, checked_to=None, include_unchecked=False, announce=True):
    """Отбирает по дню последней проверки, не меняя снимки строк."""
    if checked_from is None and checked_to is None:
        return rows

    selected = []
    for number, row in rows:
        value = row.get("Дата проверки", "").strip()
        if not value:
            if include_unchecked:
                selected.append((number, row))
            continue
        try:
            # Программа сохраняет локальное время в ISO-формате.
            checked = datetime.fromisoformat(value).date()
        except ValueError:
            if announce:
                print(f"Строка {number}: неверная «Дата проверки», строка пропущена.")
            continue
        if checked_from is not None and checked < checked_from:
            continue
        if checked_to is not None and checked > checked_to:
            continue
        selected.append((number, row))
    return selected


def run_rows(rows, process_row):
    """Перебирает строки; False от обработчика останавливает очередь."""
    # Исключения обрабатывает сам сценарий: правила остановки у этапов различаются.
    for number, row in rows:
        stop_control.check()
        if process_row(number, row) is False:
            return 1
    return 0


# Один набор правил используется исполнителями и окном предпросмотра.
QUEUE_STATUSES = {
    "fill": ("",), "ai": ("new",), "send": ("done",),
    "desktop-send": ("done",), "check": ("wait",), "review": ("thinking", "done"),
    "requirements": None,
}


def select_stage_rows(rows, command, options, ai_limit=None, apply_limit=True, announce=True):
    """Отбирает очередь этапа; лимит отправки считают после подтверждения на hh."""
    options.validate(command)
    if command not in QUEUE_STATUSES:
        raise ValueError("Для этого этапа нет очереди вакансий из таблицы.")
    pending = select_link_rows(rows, QUEUE_STATUSES[command], options.start_row)
    if command == "check":
        pending = filter_check_dates(
            pending, options.checked_from, options.checked_to,
            options.include_unchecked, announce=announce,
        )
    if not apply_limit or command in ("send", "desktop-send"):
        return pending
    limit = options.limit
    if command == "ai" and limit is None:
        if type(ai_limit) is not int or ai_limit < 1:
            raise ValueError("Лимит ИИ должен быть положительным целым числом.")
        limit = ai_limit
    return limit_rows(pending, limit)
