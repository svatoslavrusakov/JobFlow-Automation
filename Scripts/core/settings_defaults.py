"""Стандартные значения; личные настройки хранятся отдельно в data/settings.json."""

import os
from pathlib import Path

# Настройки лежат глубже; data/ остаётся в корне проекта.
PROJECT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_DIR / "data" / "settings.json"

# Пояснения используются в журнале и в редакторе пауз.
DELAY_DEFAULTS = {
    "DELAY_IMPORT_BATCH": (5.0, 5.0, "между партиями HTML-импорта в Google Sheets"),
    "DELAY_SEARCH_LOAD": (7.0, 10.0, "после открытия поиска"),
    "DELAY_SEARCH_SCROLL": (10.0, 14.0, "после прокрутки выдачи"),
    "DELAY_BEFORE_NEXT_PAGE": (10.0, 20.0, "перед переходом к следующей странице"),
    "DELAY_NEXT_PAGE_LOAD": (30.0, 38.0, "после перехода на следующую страницу"),
    "DELAY_BEFORE_PROCESSING": (15.0, 20.0, "перед обработкой вакансий"),
    "DELAY_VACANCY_LOAD": (8.0, 12.0, "после открытия вакансии"),
    "DELAY_VACANCY_SCROLL": (8.0, 14.0, "после прокрутки вакансии"),
    "DELAY_BETWEEN_VACANCIES": (15.0, 30.0, "после сохранения вакансии"),
    "DELAY_BETWEEN_RESPONSES": (15.0, 30.0, "между проверками ответов"),
    "DELAY_BEFORE_APPLICATION_CLICK": (2.0, 4.0, "после прокрутки к отклику"),
    "DELAY_APPLICATION_OPEN": (4.0, 7.0, "после нажатия «Откликнуться»"),
    "DELAY_LETTER_CHUNK": (0.4, 0.8, "между частями письма"),
    "DELAY_BEFORE_APPLICATION_SEND": (2.0, 4.0, "перед отправкой отклика"),
    "DELAY_APPLICATION_RESULT": (5.0, 8.0, "после отправки отклика"),
    "DELAY_BETWEEN_APPLICATIONS": (240.0, 360.0, "между обработанными вакансиями"),
}
TIMEOUT_DEFAULTS = {
    "CHROME_DEBUG_TIMEOUT": 3.0,
    "CHROMEDRIVER_NETWORK_TIMEOUT": 20,
    "APPLICATION_OPEN_TIMEOUT": 20.0,
    "APPLICATION_RESULT_TIMEOUT": 20.0,
    "GOOGLE_TIMEOUT": 20.0,
    "GEMINI_TIMEOUT": 60.0,
}
TIMEOUT_LABELS = {
    "CHROME_DEBUG_TIMEOUT": "Проверка порта Chrome",
    "CHROMEDRIVER_NETWORK_TIMEOUT": "Подбор драйвера",
    "APPLICATION_OPEN_TIMEOUT": "Ожидание окна отклика",
    "APPLICATION_RESULT_TIMEOUT": "Подтверждение отправки",
    "GOOGLE_TIMEOUT": "Ответ Google Таблиц",
    "GEMINI_TIMEOUT": "Ответ Gemini",
}


def default_settings():
    """Каждый вызов возвращает независимые изменяемые значения."""
    return {
        "spreadsheet": "HH_Vacancies_Analytics",
        "worksheet": "Тест_ai",
        "credentials_file": "credentials.json",
        "chrome_address": "127.0.0.1:9223",
        "chrome_executable": r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome_profile": str(Path(os.environ.get("LOCALAPPDATA", str(PROJECT_DIR / "data"))) / "Auto_hh" / "ChromeTest"),
        "search_url_file": "data/search_url.txt",
        "html_dir": "data/vacancies",
        "telegram_dir": "data/telegram",
        "pages_to_scrape": 1,
        "blacklist": ["junior", "джуниор", "стажер", "преподаватель", "c++", "lead", "тимлид"],
        "ai_provider": "gemini",
        "ai_model": "gemini-3.5-flash-lite",
        "ai_key_file": "data/ai_key.txt",
        "resume_file": "data/resume.txt",
        "prompt_file": "Scripts/ai/prompt.txt",
        "requirements_prompt_file": "Scripts/ai/requirements_prompt.txt",
        "html_prompt_file": "Scripts/ai/html_prompt.txt",
        "ai_max_rows": 50,
        "ai_pause_every": 3,
        "ai_pause_seconds": 30,
        "sound_file": "data/Duck.mp3",
        "sound_enabled": True,
        "delays": {name: list(value[:2]) for name, value in DELAY_DEFAULTS.items()},
        "timeouts": dict(TIMEOUT_DEFAULTS),
    }
