# import_hh_links.py

import sys
from pathlib import Path

from gspread.exceptions import APIError
from requests.exceptions import RequestException

from core import config
from tables import sheets
from tables.import_rows import import_rows
from core import stop_control
from core import utils
from html_tools.hh_search_html import merge_vacancy, read_search_vacancies


def read_import_source(source_path, folder=False):
    """Один файл и папка используют одинаковый парсер; подпапки не просматриваются."""
    source = Path(source_path)
    if folder:
        if not source.is_dir():
            raise ValueError("Укажите существующую папку HTML-выдач hh.")
        files = sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in (".html", ".htm"))
        if not files:
            raise ValueError("В папке нет файлов .html или .htm.")
    else:
        files = [source]
    vacancies = {}
    for path in files:
        stop_control.check()
        try:
            cards = read_search_vacancies(path, config.HH_BASE_URL)
        except (OSError, ValueError) as error:
            if not folder:
                raise
            print(f"Пропускаю файл {path.name}: {error}")
            continue
        print(f"Файл {path.name}: найдено {len(cards)} уникальных вакансий.")
        for vacancy in cards.values():
            merge_vacancy(vacancies, vacancy)
    if not vacancies:
        raise ValueError("Не найдено ни одной подходящей HTML-выдачи hh.")
    return vacancies


def import_links(sheet, vacancies):
    """Дополняет карточки до прежнего формата и использует общий импорт партиями."""
    rows = []
    for card in vacancies.values():
        vacancy = dict.fromkeys(sheets.REQUIRED_HEADERS, "")
        vacancy.update(card)
        rows.append(vacancy)
    return import_rows(sheet, rows)


def main(file_path, folder=False):
    """Проверяет HTML и паузу, затем запускает импорт в выбранный лист."""
    try:
        utils.validate_delays(required=("DELAY_IMPORT_BATCH",))
        # Сначала проверяем все источники, затем подключаемся к Google один раз.
        vacancies = read_import_source(file_path, folder=folder)
        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1

        added = import_links(sheet, vacancies)
        print(f"Добавлено: {added}. Уже было: {len(vacancies) - added}.")
        return 0
    except KeyboardInterrupt:
        print("\nИмпорт остановлен пользователем. Проверьте записанные строки.")
        return 130
    except (OSError, ValueError, APIError, RequestException) as error:
        print(f"Импорт остановлен: {error}")
        # Google мог принять партию до потери ответа; сетевую ошибку не повторяем.
        print("Если ошибка возникла при записи, проверьте последнюю партию в таблице.")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python Scripts/run.py import-html путь_к_HTML")
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
