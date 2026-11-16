"""Одно подключение к Google используется обработчиками и редактором колонок."""

import re
from urllib.parse import urlsplit

import gspread
from gspread.exceptions import APIError

from core import stop_control
from core.settings_store import check_timeout, load_settings, resolve_path


def request_with_retry(action, *args, **kwargs):
    """Повторяет только явный отказ 429; сетевой обрыв записи не повторяет."""
    pauses = (5, 15, 30, 60)
    for attempt in range(len(pauses) + 1):
        stop_control.check()
        try:
            return action(*args, **kwargs)
        except APIError as error:
            if error.response.status_code != 429 or attempt == len(pauses):
                raise
            seconds = pauses[attempt]
            print(f"Лимит Google Sheets. Повтор через {seconds} с.")
            # Остановка из интерфейса действует и во время ожидания квоты.
            stop_control.pause(seconds)


def open_spreadsheet(values=None):
    """Принимает имя, ID или ссылку на документ; ничего в таблице не изменяет."""
    values = values or load_settings()
    timeout = check_timeout(values["timeouts"]["GOOGLE_TIMEOUT"], "GOOGLE_TIMEOUT")
    client = gspread.service_account(filename=str(resolve_path(values["credentials_file"])))
    client.set_timeout(timeout)
    address = values["spreadsheet"].strip()
    if address.startswith(("http://", "https://")):
        parts = urlsplit(address)
        match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?", parts.path)
        if parts.hostname != "docs.google.com" or not match:
            raise ValueError("Нужна ссылка на документ Google Таблиц.")
        return client.open_by_key(match.group(1))
    if re.fullmatch(r"[A-Za-z0-9_-]{25,}", address):
        return client.open_by_key(address)
    return client.open(address)


def open_worksheet(values=None, worksheet=None):
    """Открывает выбранный лист через общее подключение к документу."""
    values = values or load_settings()
    title = (worksheet if worksheet is not None else values["worksheet"]).strip()
    if not title:
        raise ValueError("Укажите лист Google Таблицы.")
    return open_spreadsheet(values).worksheet(title)
