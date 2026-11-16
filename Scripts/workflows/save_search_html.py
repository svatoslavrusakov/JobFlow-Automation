"""Сохраняет страницы открытого поиска hh; таблица и отдельные вакансии не открываются."""

from argparse import ArgumentParser
from datetime import datetime

from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import HTTPError

from hh import browser
from hh import hh_search
from core import stop_control
from core import utils
from core.settings_defaults import PROJECT_DIR
from core.settings_store import write_private_file


def save_page(folder, html):
    """Выбирает свободное имя и сохраняет UTF-8 через общую атомарную запись."""
    if not html.strip():
        raise ValueError("Браузер вернул пустой HTML.")
    number = 1
    while (folder / f"sample_{number}.html").exists():
        number += 1
    output = folder / f"sample_{number}.html"
    write_private_file(output, html)
    return output


def save_search_pages(driver, folder, pages=None):
    """Начинает с текущей страницы и идёт по «Дальше» до конца или лимита."""
    driver.switch_to.default_content()
    expected_page = hh_search.get_search_page(driver.current_url)
    seen_ids, saved = set(), 0
    while pages is None or saved < pages:
        stop_control.check()
        items = hh_search.read_search_page(driver, expected_page)
        if not items:
            raise ValueError("Выдача не подтверждена: карточки не найдены.")
        page_ids = {item["id"] for item in items}
        if not page_ids - seen_ids:
            raise ValueError("Повторилась прежняя выдача. Проверьте переход между страницами.")
        # Проверяем страницу до и после получения снимка: URL мог обновиться раньше DOM.
        hh_search.check_search_page(driver, expected_page)
        html = driver.page_source
        browser.check_authorization(driver)
        hh_search.check_search_page(driver, expected_page)
        output = save_page(folder, html)
        saved += 1
        seen_ids.update(page_ids)
        print(f"Страница {expected_page[2] + 1}: сохранено {len(page_ids)} вакансий — {output}")
        if saved == pages:
            break
        expected_page = hh_search.go_to_next_search_page(driver)
        if expected_page is None:
            break
    return saved


def main(pages=None):
    """Подключается к Chrome и использует уже открытый поиск, без чтения search_url.txt."""
    try:
        if pages is not None and (type(pages) is not int or pages < 1):
            raise ValueError("Количество страниц должно быть целым числом от 1.")
        utils.validate_delays(required=(
            "DELAY_SEARCH_SCROLL", "DELAY_BEFORE_NEXT_PAGE", "DELAY_NEXT_PAGE_LOAD",
        ))
        driver = browser.connect_browser()
        if driver is None:
            return 1
        # Дату фиксируем один раз: весь запуск сохраняется в одной папке.
        folder = PROJECT_DIR / "Examples" / f"Examples_search_{datetime.now():%d_%m_%y}"
        print(f"Папка сохранения: {folder}")
        count = save_search_pages(driver, folder, pages)
        print(f"Сохранено страниц: {count}.")
        return 0
    except KeyboardInterrupt:
        print("Сохранение остановлено пользователем. Готовые HTML остаются в папке.")
        return 130
    except (OSError, ValueError, WebDriverException, HTTPError) as error:
        print(f"Сохранение поиска остановлено: {error}")
        return 1


def cli():
    """Читает параметры прежней команды сохранения выдачи."""
    parser = ArgumentParser(description="Сохранить HTML страниц открытого поиска hh.")
    parser.add_argument("--pages", type=int, help="Сколько страниц сохранить; без параметра — до конца поиска")
    return main(parser.parse_args().pages)


if __name__ == "__main__":
    raise SystemExit(cli())
