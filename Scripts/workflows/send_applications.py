# send_applications.py

from gspread.exceptions import APIError
from requests.exceptions import RequestException
from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import HTTPError

from hh import application_sender
from tables import application_sheet
from hh import browser
from core import config
from tables import duplicates
from tables import sheets
from core import stop_control
from core import utils
from tables.application_sheet import read_send_queue
from core.run_options import RunOptions


def send_one_row(
    sheet, driver, id_rows, stats, row_number, row, pause_before_visit=False,
):
    """Возвращает браузер, остановку и результат посещения hh либо None."""
    try:
        item = duplicates.prepare_link(row_number, row, id_rows)
        if item is not None:
            # Письмо читаем только у выбранной строки.
            _, row = application_sheet.check_application_row(
                sheet, row_number, row,
            )
    except ValueError as error:
        print(f"Строка {row_number}: {error}")
        stats["errors"] += 1
        stats["pending"] -= 1
        return driver, False, None

    if item is None:
        stats["skipped"] += 1
        stats["pending"] -= 1
        return driver, False, None

    # Подключаемся к Chrome только перед первым настоящим посещением hh.
    if driver is None:
        driver = browser.connect_browser()
        if driver is None:
            stats["errors"] += 1
            stats["pending"] -= 1
            return driver, True, None

    print(f"\nСтрока {row_number}: обрабатываю {item['link']}")
    # Ждём перед следующим посещением hh, а не после последней строки.
    if pause_before_visit:
        utils.human_delay(config.DELAY_BETWEEN_APPLICATIONS, cancelable=True)
    outcome = application_sender.process_application(
        driver, sheet, row_number, row, item,
    )
    stats["saved"] += 1
    if outcome == "sent":
        stats["sent"] += 1
    stats["pending"] -= 1
    return driver, False, outcome


def send_applications(options=None):
    options = options or RunOptions()
    options.validate("send")
    stats = None
    # Нужно для учёта ошибки, если запуск оборвался посреди одной строки.
    active_row = False

    try:
        utils.validate_delays(required=(
            "DELAY_VACANCY_LOAD", "DELAY_BEFORE_APPLICATION_CLICK",
            "DELAY_APPLICATION_OPEN", "DELAY_LETTER_CHUNK",
            "DELAY_BEFORE_APPLICATION_SEND", "DELAY_APPLICATION_RESULT",
            "DELAY_BETWEEN_APPLICATIONS",
        ), timeouts=("APPLICATION_OPEN_TIMEOUT", "APPLICATION_RESULT_TIMEOUT"))
        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1

        rows, pending = read_send_queue(sheet, options)
        stats = utils.create_stats(len(pending))
        stats["sent"] = 0
        if not pending:
            print("Нет ссылок со статусом done.")
            return 0

        id_rows = duplicates.build_id_index(rows)
        driver = None
        print(f"Найдено вакансий для отклика: {len(pending)}")
        visited_before = False

        for row_number, row in pending:
            stop_control.check()
            active_row = True
            driver, stop, outcome = send_one_row(
                sheet, driver, id_rows, stats, row_number, row,
                pause_before_visit=visited_before,
            )
            active_row = False
            if stop:
                return 1
            if outcome is not None:
                visited_before = True
            if options.limit is not None and stats["sent"] >= options.limit:
                print(f"Лимит новых откликов достигнут: {stats['sent']}.")
                break

        return 1 if stats["errors"] else 0

    except KeyboardInterrupt:
        print("\nЗапуск остановлен. При перезапуске сначала проверяется статус на hh.")
        return 130
    except (
        ValueError, RuntimeError, WebDriverException,
        HTTPError, APIError, RequestException, OSError,
    ) as error:
        print(f"Запуск остановлен: {error}")
        if active_row:
            print("При перезапуске сначала проверяется статус последней вакансии на hh.")
        if stats and active_row:
            stats["errors"] += 1
            stats["pending"] -= 1
        return 1
    finally:
        utils.print_summary(stats)


if __name__ == "__main__":
    raise SystemExit(send_applications())
