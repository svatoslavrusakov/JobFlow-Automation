"""Ручная проверка письма: чтение строки и запись только письма со статусом."""

from gspread.utils import rowcol_to_a1

from tables import sheets
from core import utils
from core.row_queue import QUEUE_STATUSES

REVIEW_HEADERS = ("ID", "Ссылка", "Статус", "Сопроводительное")
CONTEXT_FIELDS = (
    "Компания", "Заголовок", "Описание", "Зарплата",
    "Требования к отклику", "Подводные камни", "Оценка ИИ",
)
# Сравниваем поля, по которым пользователь принимал решение; заметки не затираем.
WATCHED_FIELDS = REVIEW_HEADERS + CONTEXT_FIELDS


def normalize_letter(text):
    """Tkinter и оба отправщика используют перевод строки LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_review(sheet, number, queued):
    """Читает свежую строку; её номер мог сместиться после вставки в Google."""
    headers = sheets.read_headers(sheet, required_headers=REVIEW_HEADERS)
    current = sheets.read_current_row(sheet, number, headers)
    for field in ("ID", "Ссылка"):
        if current[field].strip() != queued[field].strip():
            raise ValueError("На этом месте уже другая вакансия. Обновите очередь.")
    # Новый статус показываем как есть: отправленная строка откроется только для чтения.
    return current


def require_editable(row):
    """Проверяет общие ограничения редактора до показа кнопок и перед записью."""
    if row["Статус"].strip() not in QUEUE_STATUSES["review"]:
        raise ValueError("Редактирование доступно только для thinking и done.")
    for field in WATCHED_FIELDS:
        if row.get(field, "").lstrip().startswith("="):
            raise ValueError(f"В поле «{field}» находится формула. Доступен только просмотр.")
    vacancy_id, _ = utils.parse_vacancy_link(row["Ссылка"])
    if row["ID"].strip() not in ("", vacancy_id):
        raise ValueError("ID не совпадает со ссылкой. Доступен только просмотр.")


def build_review_values(before, current, text, approve):
    """Готовит два изменяемых поля после проверки снимка и текста."""
    for field in WATCHED_FIELDS:
        if current.get(field, "") != before.get(field, ""):
            raise ValueError(f"Поле «{field}» изменилось. Перечитайте строку перед одобрением.")
    require_editable(current)
    if type(approve) is not bool:
        raise ValueError("Нужно явно выбрать сохранение или одобрение.")
    text = normalize_letter(text)
    if not text.strip() or text.lstrip().startswith("="):
        raise ValueError("Письмо должно содержать текст и не начинаться со знака =.")
    if any(ord(char) < 32 and char != "\n" for char in text):
        raise ValueError("В письме есть управляющие символы. Уберите их перед сохранением.")
    return {"Сопроводительное": text, "Статус": "done" if approve else "thinking"}


def save_review(sheet, number, before, text, approve):
    """Перечитывает контекст и сохраняет письмо со статусом одним запросом."""
    headers = sheets.read_headers(sheet, required_headers=REVIEW_HEADERS)
    current = sheets.read_current_row(sheet, number, headers)
    wanted = build_review_values(before, current, text, approve)
    updates = [
        {"range": rowcol_to_a1(number, headers.index(field) + 1), "values": [[value]]}
        for field, value in wanted.items() if current[field] != value
    ]
    if updates:
        # RAW сохраняет буквальный текст. Даты, заметки и результаты ИИ не записываем.
        # При ошибке запрос автоматически не повторяется: результат мог сохраниться.
        sheet.batch_update(updates, value_input_option="RAW")
    return {**current, **wanted}
