# collect_html.py

from functools import partial
from urllib.parse import urlsplit

from gspread.exceptions import APIError
from requests.exceptions import RequestException
from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import HTTPError

from hh import browser
from core import config
from tables import sheets
from core import utils
from html_tools.html_storage import has_snapshot, save_snapshot
from core.row_queue import limit_rows, run_rows, select_link_rows
from core.run_options import RunOptions
from core.settings_defaults import PROJECT_DIR


def validate_site_url(value):
    """Проверяет адрес без очистки значимых параметров и фрагмента."""
    # Убираем только пробелы по краям; параметры и # могут определять вакансию.
    url = value.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Нужна полная ссылка http:// или https://.")
    return url


def read_page_html(driver, url):
    """Открывает страницу и возвращает её текущий DOM после пауз."""
    # Предыдущая операция могла оставить браузер внутри iframe.
    driver.switch_to.default_content()
    driver.get(url)
    utils.human_delay(config.DELAY_VACANCY_LOAD)
    # Прокрутка помогает подгрузить контент, но не доказывает готовность всей страницы.
    driver.execute_script("window.scrollBy(0, 1000);")
    utils.human_delay(config.DELAY_VACANCY_SCROLL)
    # Конечный URL может отличаться после редиректа. iframe и shadow DOM отдельно не читаем.
    return driver.current_url, driver.page_source


def save_html_row(driver, output_dir, number, row):
    """Обрабатывает одну внешнюю ссылку, ничего не записывая в таблицу."""
    url = validate_site_url(row["Ссылка"])
    print(f"Строка {number}: проверяю снимок для {url}")
    # Одна ссылка могла повториться в очереди: предыдущая строка уже создала снимок.
    if has_snapshot(output_dir, url):
        print(f"Строка {number}: HTML уже сохранён.")
        return True

    final_url, html = read_page_html(driver, url)
    # Chrome может показать служебную страницу вместо запрошенного сайта.
    # Проверяем формат адреса; содержание страницы ошибки или капчи здесь не распознаётся.
    validate_site_url(final_url)
    folder = save_snapshot(output_dir, url, final_url, html)
    print(f"Строка {number}: HTML сохранён в {folder}")
    utils.human_delay(config.DELAY_BETWEEN_VACANCIES, cancelable=True)
    return True


def select_missing_rows(rows, output_dir):
    """Отсекает готовые снимки ещё до подключения к Chrome."""
    # Так полностью готовая очередь завершится без подключения к браузеру.
    pending = []
    for number, row in rows:
        try:
            url = validate_site_url(row["Ссылка"])
            if has_snapshot(output_dir, url):
                print(f"Строка {number}: HTML уже сохранён.")
            else:
                pending.append((number, row))
        except ValueError as error:
            raise ValueError(f"Строка {number}: {error}") from error
    return pending


def collect_html(options=None):
    """Подготавливает очередь и передаёт строки общему обработчику."""
    options = options or RunOptions()
    options.validate("collect-html")
    utils.validate_delays(required=(
        "DELAY_VACANCY_LOAD", "DELAY_VACANCY_SCROLL", "DELAY_BETWEEN_VACANCIES",
    ))
    sheet = sheets.init_google_sheet()
    if sheet is None:
        return 1

    # Этому этапу не нужны ID и описания: из таблицы берём только очередь ссылок.
    fields = ("Ссылка", "Статус")
    rows = sheets.read_vacancy_rows(sheet, fields=fields, required_headers=fields)
    # Относительную папку считаем от корня проекта, а не от текущей консоли.
    output_dir = PROJECT_DIR / config.HTML_DIR
    pending = select_missing_rows(
        select_link_rows(rows, start_row=options.start_row), output_dir,
    )
    # Уже сохранённые снимки не расходуют лимит этого запуска.
    pending = limit_rows(pending, options.limit)
    if not pending:
        print("Нет несохранённых ссылок с пустым статусом.")
        return 0

    driver = browser.connect_browser()
    if driver is None:
        return 1
    # Фиксируем браузер и папку; номер и данные строки подставит run_rows.
    handler = partial(save_html_row, driver, output_dir)
    return run_rows(pending, handler)


def main(options=None):
    try:
        return collect_html(options)
    except KeyboardInterrupt:
        print("\nСохранение HTML остановлено пользователем.")
        return 130
    # При сбое останавливаем этап; опубликованные снимки сохраняются для перезапуска.
    except (
        OSError, ValueError, APIError, RequestException, WebDriverException, HTTPError,
    ) as error:
        print(f"Сохранение HTML остановлено: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
