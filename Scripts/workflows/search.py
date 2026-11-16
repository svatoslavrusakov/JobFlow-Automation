"""Запуск поиска: проверить настройки, собрать ссылки и обработать новые вакансии."""

from hh import browser
from core import config
from tables import duplicates
from hh import hh_search
from tables import sheets
from core import stop_control
from core import utils
from hh import vacancy_processor


def process_search_items(driver, sheet, items, existing_ids, stats):
    """Пропускает известные вакансии и сохраняет новые по одной."""
    for item in items:
        stop_control.check()
        vacancy_id = item["id"]
        title = item["title"]

        if any(bad_word in title.lower() for bad_word in config.BLACK_LIST):
            print(f"[-] ПРОПУСК (Черный список): {title}")
            stats["skipped"] += 1
            stats["pending"] -= 1
            continue

        if vacancy_id in existing_ids:
            print(f"[=] ДУБЛИКАТ (ID {vacancy_id}): {title}")
            stats["skipped"] += 1
            stats["pending"] -= 1
            continue

        print(f"\n[+] НОВАЯ ВАКАНСИЯ! Открываю (ID: {vacancy_id}): {title}")
        # False требует остановки; ошибка уже учтена общим обработчиком.
        if not vacancy_processor.process_vacancy(
            driver, sheet, item, stats, existing_ids=existing_ids,
        ):
            return False
    return True


def process_vacancies():
    """Запускает поиск и передаёт новые вакансии общему обработчику."""
    stats = None

    try:
        # Ошибку настройки выявляем один раз, до запросов к сайтам.
        try:
            utils.validate_delays(required=(
                "DELAY_SEARCH_LOAD", "DELAY_SEARCH_SCROLL",
                "DELAY_BEFORE_NEXT_PAGE", "DELAY_NEXT_PAGE_LOAD",
                "DELAY_BEFORE_PROCESSING", "DELAY_VACANCY_LOAD",
                "DELAY_VACANCY_SCROLL", "DELAY_BETWEEN_VACANCIES",
            ))
        except ValueError as error:
            print(f"Ошибка настройки пауз: {error}")
            return 1

        # Неверный или отсутствующий локальный адрес выявляем до Google и Chrome.
        try:
            search_url = config.read_search_url()
            hh_search.get_search_page(search_url)
        except ValueError as error:
            print(f"Ошибка ссылки поиска: {error}")
            return 1

        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1

        try:
            rows = sheets.read_vacancy_rows(sheet)
            existing_ids = set(duplicates.build_id_index(rows))
        except Exception as error:
            print(f"Ошибка чтения строк: {error}")
            return 1

        print(f"Загружено известных ID: {len(existing_ids)}.\n")
        driver = browser.connect_browser()
        if driver is None:
            return 1

        vacancies_to_process = hh_search.collect_search_links(driver, search_url)
        if vacancies_to_process is None:
            return 1

        stats = utils.create_stats(len(vacancies_to_process))
        print(f"\n✅ ИТОГО СОБРАНО ВАКАНСИЙ ДЛЯ ПРОВЕРКИ: {len(vacancies_to_process)}")
        utils.human_delay(config.DELAY_BEFORE_PROCESSING)

        if not process_search_items(
            driver, sheet, vacancies_to_process, existing_ids, stats,
        ):
            return 1

        print("\nОбработка списка завершена.")
        return 1 if stats["errors"] else 0

    except KeyboardInterrupt:
        print("\nЗапуск остановлен пользователем.")
        return 130
    finally:
        # finally выполняется также при return и неожиданных исключениях.
        utils.print_summary(stats)


if __name__ == "__main__":
    raise SystemExit(process_vacancies())
