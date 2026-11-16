"""Параметры текущего процесса из общего локального файла настроек."""

import os

from core.settings_defaults import DELAY_DEFAULTS, PROJECT_DIR
from core.settings_store import load_settings, resolve_path

# Окно и консоль читают одинаковые параметры при запуске.
VALUES = load_settings()

HH_BASE_URL = "https://rostov.hh.ru"
CREDENTIALS_FILE = str(resolve_path(VALUES["credentials_file"]))
SPREADSHEET_NAME = VALUES["spreadsheet"]
DEFAULT_WORKSHEET_NAME = VALUES["worksheet"]
WORKSHEET_NAME = os.environ.get("AUTO_HH_WORKSHEET") or DEFAULT_WORKSHEET_NAME
CHROME_DEBUG_PORT = VALUES["chrome_address"]
HTML_DIR = str(resolve_path(VALUES["html_dir"]))
PAGES_TO_SCRAPE = VALUES["pages_to_scrape"]
BLACK_LIST = VALUES["blacklist"]
SEARCH_URL_FILE = resolve_path(VALUES["search_url_file"])

# Имена DELAY_* сохранены: обработчики не зависят от интерфейса настроек.
for name, description in DELAY_DEFAULTS.items():
    pair = VALUES["delays"][name]
    # Форму и значения проверит этап, использующий эту настройку.
    globals()[name] = (*pair, description[2]) if isinstance(pair, (list, tuple)) and len(pair) == 2 else pair
for name, value in VALUES["timeouts"].items():
    if name == "CHROMEDRIVER_NETWORK_TIMEOUT" and type(value) in (int, float) and value % 1 == 0:
        value = int(value)
    globals()[name] = value


def read_search_url():
    """Ссылка поиска остаётся отдельным локальным файлом."""
    try:
        url = SEARCH_URL_FILE.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Не удалось прочитать {SEARCH_URL_FILE}.") from error
    if not url:
        raise ValueError(f"Файл {SEARCH_URL_FILE} пуст.")
    return url
