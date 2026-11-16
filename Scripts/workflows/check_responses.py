# check_responses.py

from datetime import datetime

from gspread.exceptions import APIError
from requests.exceptions import RequestException
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from urllib3.exceptions import HTTPError

from hh import browser
from core import config
from tables import duplicates
from hh import response_reader
from tables import response_sheet
from tables import sheets
from core import stop_control
from core import utils
from core.row_queue import select_stage_rows
from core.run_options import RunOptions


def read_wait_queue(sheet, headers, options=None):
    """Читает только нужные колонки и выбирает отклики со статусом wait."""
    fields = ("ID", "Ссылка", "Статус", "Дата проверки")
    # Старую отметку архива читаем для переноса, но больше не записываем.
    if "Доступность" in headers:
        fields += ("Доступность",)
    rows = sheets.read_vacancy_rows(sheet, fields=fields, headers=headers)
    options = options or RunOptions()
    return rows, select_stage_rows(rows, "check", options)


def count_error(stats):
    """Учитывает ошибку и уменьшает число оставшихся строк."""
    stats["errors"] += 1
    stats["pending"] -= 1


def check_response_row(sheet, driver, id_rows, stats, row_number, row):
    """Проверяет одну строку; возвращает браузер и признак остановки."""
    try:
        item = duplicates.prepare_link(row_number, row, id_rows)
    except ValueError as error:
        print(f"Строка {row_number}: ошибка — {error}")
        count_error(stats)
        return driver, False

    if item is None:
        stats["skipped"] += 1
        stats["pending"] -= 1
        return driver, False

    visited = False
    try:
        if row.get("Доступность", "").strip() == "archive":
            # Подтверждённый ранее архив переносим без открытия hh и новой даты.
            status = "archive"
            checked_at = None
            print(f"Строка {row_number}: переношу прежнюю отметку архива.")
        else:
            print(f"\nСтрока {row_number}: проверяю {item['link']}")
            if driver is None:
                driver = browser.connect_browser()
                if driver is None:
                    count_error(stats)
                    return driver, True

            visited = True
            result = response_reader.read_response(driver, item)
            status = response_reader.get_response_status(result)
            checked_at = datetime.now()

        changed = response_sheet.update_response_row(
            sheet, row_number, row, item["id"], status, checked_at,
        )
    except PermissionError as error:
        print(f"Проверка остановлена: {error}")
        count_error(stats)
        return driver, True
    except (NoSuchElementException, StaleElementReferenceException, ValueError) as error:
        print(f"Строка {row_number}: ошибка — {error}")
        count_error(stats)
    except (WebDriverException, HTTPError) as error:
        print(f"Ошибка работы с браузером: {error}")
        print("Запуск остановлен. Проверьте Chrome.")
        count_error(stats)
        return driver, True
    except (APIError, RequestException, OSError) as error:
        print(f"Ошибка обновления строки {row_number}: {error}")
        print("Запуск остановлен. Проверьте результат в таблице.")
        count_error(stats)
        return driver, True
    except Exception:
        count_error(stats)
        raise
    else:
        if changed:
            print(f"Строка {row_number}: статус {status}.")
            stats["saved"] += 1
        else:
            print(f"Строка {row_number}: без изменений.")
            stats["skipped"] += 1
        stats["pending"] -= 1

    if visited:
        utils.human_delay(config.DELAY_BETWEEN_RESPONSES, cancelable=True)
    return driver, False


def check_responses(options=None):
    """Готовит очередь и последовательно проверяет ожидающие отклики."""
    options = options or RunOptions()
    options.validate("check")
    stats = None
    try:
        try:
            utils.validate_delays(required=(
                "DELAY_VACANCY_LOAD", "DELAY_BETWEEN_RESPONSES",
            ))
        except ValueError as error:
            print(f"Ошибка настройки пауз: {error}")
            return 1

        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1

        try:
            headers = sheets.read_headers(sheet)
            if "Дата проверки" not in headers:
                print("Добавьте пустую колонку «Дата проверки» в выбранный лист.")
                return 1
            rows, pending_rows = read_wait_queue(sheet, headers, options)
        except (APIError, RequestException, OSError, ValueError) as error:
            print(f"Ошибка чтения таблицы: {error}")
            return 1

        stats = utils.create_stats(len(pending_rows))
        if not pending_rows:
            print("Нет строк wait, подходящих под параметры отбора.")
            return 0

        id_rows = duplicates.build_id_index(rows)
        # Chrome открываем только перед первым посещением hh.
        driver = None
        print(f"Найдено откликов для проверки: {len(pending_rows)}")
        for row_number, row in pending_rows:
            stop_control.check()
            driver, stop = check_response_row(
                sheet, driver, id_rows, stats, row_number, row,
            )
            if stop:
                return 1

        print("\nПроверка ответов завершена.")
        return 1 if stats["errors"] else 0

    except KeyboardInterrupt:
        print("\nЗапуск остановлен пользователем.")
        return 130
    finally:
        utils.print_summary(stats)


if __name__ == "__main__":
    raise SystemExit(check_responses())
