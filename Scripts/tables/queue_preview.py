"""Снимок очереди из Google Таблицы; браузер и генератор здесь не запускаются."""

from datetime import datetime

from tables import application_sheet
from core import config
from tables import duplicates
from tables import google_connection
from tables import letter_review
from tables import sheets
from ai import sheet as ai_sheet
from core.row_queue import QUEUE_STATUSES, select_stage_rows

PREVIEW_STAGES = (
    ("fill", "Заполнить по ссылкам"),
    ("ai", "Подготовить письма"),
    ("review", "Просмотреть письма"),
    ("send", "Отправить отклики — оба способа"),
    ("check", "Проверить ответы"),
)
PAGE_SIZE = 25


def selection_reason(number, row, command, options, before_limit, selected):
    """Поясняет результат общего отбора, не вычисляя фильтр дат заново."""
    if number < options.start_row:
        return "Раньше начальной строки."
    if not row["Ссылка"].strip():
        return "Нет ссылки."
    if row["Статус"].strip() not in QUEUE_STATUSES[command]:
        expected = ", ".join(status or "пустой" for status in QUEUE_STATUSES[command])
        return f"Нужен статус: {expected}."
    if number not in before_limit:
        return "Дата проверки не прошла фильтр."
    if number not in selected:
        return "За пределами лимита."
    return ""


def prepare_snapshot(rows, command, options, ai_limit=None):
    """Использует тот же отбор и проверку ссылок, что рабочие обработчики."""
    before = select_stage_rows(rows, command, options, ai_limit, apply_limit=False, announce=False)
    pending = select_stage_rows(rows, command, options, ai_limit, announce=False)
    before_numbers, selected = {number for number, _ in before}, {number for number, _ in pending}
    # ИИ сейчас не фильтрует дубли; предпросмотр сохраняет его поведение.
    ids = duplicates.build_id_index(rows) if command != "ai" else {}
    entries = []
    for number, row in rows:
        if not any(row[field].strip() for field in ("ID", "Ссылка", "Статус")):
            continue
        reason = selection_reason(number, row, command, options, before_numbers, selected)
        decision = "Пропуск" if reason else "Кандидат"
        if not reason:
            try:
                _, reason = duplicates.inspect_link(number, row, ids)
                if reason:
                    decision = "Пропуск"
            except ValueError as error:
                decision, reason = "Ошибка", str(error)
        entries.append({
            "number": number, "source": row, "selected": number in selected,
            "decision": decision, "reason": reason or "",
        })
    return entries


def load_preview(worksheet, command, options):
    options.validate(command)
    if command not in dict(PREVIEW_STAGES):
        raise ValueError("Для этого этапа предпросмотр пока не предусмотрен.")
    sheet = google_connection.open_worksheet(worksheet=worksheet)
    required = sheets.REQUIRED_HEADERS
    if command == "ai":
        required = ai_sheet.AI_HEADERS
    elif command == "review":
        required = letter_review.REVIEW_HEADERS
    headers = sheets.read_headers(sheet, required_headers=required)
    if command == "send":
        missing = [name for name in ("Сопроводительное", "Комментарий") if name not in headers]
        if missing:
            raise ValueError("Добавьте колонки: " + ", ".join(missing))
    fields = ("ID", "Ссылка", "Статус", "Дата проверки") if command == "check" else ("ID", "Ссылка", "Статус")
    rows = sheets.read_vacancy_rows(sheet, fields=fields, required_headers=required, headers=headers)
    ai_limit = config.VALUES["ai_max_rows"]
    return {
        "sheet": sheet, "headers": headers, "command": command, "options": options,
        "title": sheet.title, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entries": prepare_snapshot(rows, command, options, ai_limit),
        "limit": options.limit if options.limit is not None or command != "ai" else ai_limit,
    }


def describe_row(entry, current, command, headers):
    """В результате остаются только подписи и наличие письма, а не его полный текст."""
    decision, reason = entry["decision"], entry["reason"]
    watched = ("ID", "Ссылка", "Статус", "Дата проверки") if command == "check" else ("ID", "Ссылка", "Статус")
    if any(current[field].lstrip().startswith("=") for field in watched):
        decision, reason = "Ошибка", "В ID, ссылке, статусе или дате находится формула."
    elif any(current[field].strip() != entry["source"][field].strip() for field in watched):
        decision, reason = "Изменена", "Строка изменилась после чтения очереди. Обновите просмотр."
    elif decision == "Кандидат":
        try:
            if command == "send":
                application_sheet.check_application_values(current, entry["source"])
            elif command == "ai":
                ai_sheet.require_empty_results(current)
        except ValueError as error:
            decision, reason = "Пропуск", str(error)
    letter = current.get("Сопроводительное", "")
    present = "Нет колонки" if "Сопроводительное" not in headers else (
        "Формула" if letter.lstrip().startswith("=") else "Есть" if letter.strip() else "Нет"
    )
    return {
        "number": entry["number"], "id": current["ID"], "company": current.get("Компания", ""),
        "title": current.get("Заголовок", ""), "status": current["Статус"], "letter": present,
        "decision": decision, "reason": reason, "link": current["Ссылка"],
        "checked": current.get("Дата проверки", ""),
    }


def read_preview_page(snapshot, entries):
    """Дополняет только видимую страницу, не читая описания вакансий."""
    if not entries:
        return []
    sheet, command = snapshot["sheet"], snapshot["command"]
    headers = sheets.read_headers(sheet, required_headers=())
    if headers != snapshot["headers"]:
        raise ValueError("Заголовки изменились. Обновите очередь.")
    fields = ["ID", "Ссылка", "Статус", "Компания", "Заголовок", "Сопроводительное"]
    if command == "ai":
        fields += [name for name in ai_sheet.AI_COLUMNS if name != "Сопроводительное"]
    if command == "check":
        fields.append("Дата проверки")
    values = sheets.read_row_fields(sheet, [entry["number"] for entry in entries], headers, fields)
    return [describe_row(entry, values[entry["number"]], command, headers) for entry in entries]
