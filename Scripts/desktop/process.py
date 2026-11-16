"""Общая очередь таблицы, отдельный способ управления Chrome."""

import importlib.util

from gspread.exceptions import APIError
from requests.exceptions import RequestException

from tables import application_sheet
from core import config
from tables import duplicates
from tables import sheets
from core import stop_control
from core import utils
from desktop import profile
from core.run_options import RunOptions


def require_dependencies():
    missing = [
        name for name in ("pyautogui", "pynput", "pyperclip", "cv2", "PIL")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise ValueError("Установите экранный режим: python -m pip install -r requirements-desktop.txt")


def prepare_items(rows, pending, stats):
    """Ошибки ссылок и дубли учитываются до обращения к экрану."""
    ids = duplicates.build_id_index(rows)
    items = []
    for number, row in pending:
        try:
            item = duplicates.prepare_link(number, row, ids)
        except ValueError as error:
            # Ошибка одной ссылки не отменяет остальные строки очереди.
            print(f"Строка {number}: {error}")
            stats["errors"] += 1
            stats["pending"] -= 1
            continue
        if item is None:
            stats["skipped"] += 1
            stats["pending"] -= 1
        else:
            items.append((number, row, item))
    return items


def connect_screen(values):
    """Привязывается к Chrome, который пользователь сам выбрал во время отсчёта."""
    from desktop.window import ChromeWindow
    from desktop.controls import Controls
    from desktop.screen import Screen
    print("Ввод через экран; Selenium и порт отладки не используются.")
    print(f"Переключитесь в нужный Chrome: старт через {values['countdown']:g} с. Escape — остановка.")
    stop_control.pause(values["countdown"])
    window = ChromeWindow()
    window.require_geometry(values)
    return Controls(window, values["typing_interval"]), Screen(window, values)


def process_queue(sheet, items, values, options, submit, stats):
    from desktop.application import fill_open_dialog, send_one
    controls, screen = connect_screen(values)
    visited = False
    for number, original, item in items:
        stop_control.check()
        try:
            _, row = application_sheet.check_application_row(sheet, number, original)
            print(f"\nСтрока {number}: {'отправка' if submit else 'проба без отправки'}, ID {item['id']}")
            if not submit:
                if not fill_open_dialog(controls, screen, item, row):
                    raise RuntimeError("Распознана анкета. Проба остановлена без отправки.")
                stats["pending"] -= 1
                print("Проба выполнена: письмо заполнено. Финальная кнопка не нажималась; таблица не изменена.")
                return 0
            if visited:
                controls.delay(config.DELAY_BETWEEN_APPLICATIONS)
            outcome = send_one(sheet, number, row, item, controls, screen)
        except Exception:
            # Считаем ошибку именно начатой строки; подробности выводит main.
            stats["errors"] += 1
            stats["pending"] -= 1
            raise
        visited = True
        stats["saved"] += 1
        stats["pending"] -= 1
        if outcome == "sent":
            stats["sent"] += 1
        print(f"Строка {number}: {outcome}.")
        if options.limit is not None and stats["sent"] >= options.limit:
            break
    return 0


def main(options=None, submit=False):
    options = options or RunOptions()
    options.validate("desktop-send")
    stats = None
    try:
        require_dependencies()
        values = profile.load_profile()
        profile.validate(values, submit=submit)
        utils.validate_delays(required=(
            "DELAY_VACANCY_LOAD", "DELAY_BEFORE_APPLICATION_CLICK", "DELAY_APPLICATION_OPEN",
            "DELAY_BEFORE_APPLICATION_SEND", "DELAY_APPLICATION_RESULT", "DELAY_BETWEEN_APPLICATIONS",
        ), timeouts=("APPLICATION_OPEN_TIMEOUT", "APPLICATION_RESULT_TIMEOUT"))
        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1
        rows, pending = application_sheet.read_send_queue(sheet, options)
        stats = utils.create_stats(len(pending))
        stats["sent"] = 0
        if not pending:
            print("Нет ссылок со статусом done.")
            return 0
        items = prepare_items(rows, pending, stats)
        if items:
            result = process_queue(sheet, items, values, options, submit, stats)
            if result:
                return result
        # Продолжаем пригодные строки, но не скрываем ошибки в коде завершения.
        return 1 if stats["errors"] else 0
    except KeyboardInterrupt:
        print("Экранный запуск остановлен пользователем.")
        return 130
    except (ValueError, RuntimeError, OSError, ImportError, APIError, RequestException) as error:
        print(f"Экранный запуск остановлен: {error}")
        print("При неизвестном результате проверьте hh перед повторной отправкой.")
        return 1
    finally:
        utils.print_summary(stats)
