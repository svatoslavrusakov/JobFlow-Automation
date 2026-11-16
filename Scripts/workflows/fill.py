# process_links.py

from functools import partial

from hh import browser
from core import config
from tables import duplicates
from tables import sheets
from core import utils
from hh import vacancy_processor
from core.row_queue import run_rows, select_stage_rows
from core.run_options import RunOptions


def process_hh_row(driver, sheet, id_rows, stats, row_number, row):
    """Проверяет одну строку hh; False требует остановить общий обход."""
    try:
        item = duplicates.prepare_link(row_number, row, id_rows)
    except ValueError as error:
        print(f"Строка {row_number}: ошибка — {error}")
        stats["errors"] += 1
        stats["pending"] -= 1
        utils.human_delay(config.DELAY_BETWEEN_VACANCIES, cancelable=True)
        return True

    if item is None:
        stats["skipped"] += 1
        stats["pending"] -= 1
        return True

    print(f"\nСтрока {row_number}: открываю {item['link']}")
    return vacancy_processor.process_vacancy(
        driver, sheet, item, stats,
        row_number=row_number, original_link=row["Ссылка"],
    )


def process_links(options=None):
    options = options or RunOptions()
    options.validate("fill")
    stats = None

    try:
        try:
            utils.validate_delays(required=(
                "DELAY_VACANCY_LOAD", "DELAY_VACANCY_SCROLL",
                "DELAY_BETWEEN_VACANCIES",
            ))
        except ValueError as error:
            print(f"Ошибка настройки пауз: {error}")
            return 1

        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1

        try:
            rows = sheets.read_vacancy_rows(sheet)
        except Exception as error:
            print(f"Ошибка чтения строк: {error}")
            return 1

        # Любой непустой статус исключает строку до формирования очереди.
        pending_rows = select_stage_rows(rows, "fill", options)
        stats = utils.create_stats(len(pending_rows))
        if not pending_rows:
            print("Нет ссылок с пустым статусом.")
            return 0

        # В индексе остаются и обработанные, и исключённые строки.
        id_rows = duplicates.build_id_index(rows)
        driver = browser.connect_browser()
        if driver is None:
            return 1

        print(f"Найдено строк для обработки: {len(pending_rows)}")
        # partial связывает общие параметры, run_rows передаёт номер и строку.
        handler = partial(process_hh_row, driver, sheet, id_rows, stats)
        if run_rows(pending_rows, handler):
            return 1

        print("\nОбработка ссылок завершена.")
        return 1 if stats["errors"] else 0

    except KeyboardInterrupt:
        print("\nЗапуск остановлен пользователем.")
        return 130
    finally:
        utils.print_summary(stats)


if __name__ == "__main__":
    raise SystemExit(process_links())
