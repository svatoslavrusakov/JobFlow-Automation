"""Чтение поисковой выдачи hh и переход между её страницами."""

from urllib.parse import parse_qs, urlsplit

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

from urllib3.exceptions import HTTPError

from hh import browser
from core import config
from core import stop_control
from core import utils


def get_search_page(url):
    """Возвращает домен, путь и номер страницы поиска."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if (
        parts.scheme not in ("http", "https")
        or not utils.is_hh_host(host)
        or parts.path.rstrip("/") != "/search/vacancy"
    ):
        raise ValueError("Открыта не страница поиска hh.")

    # На первой странице параметр page обычно отсутствует и означает 0.
    pages = parse_qs(parts.query, keep_blank_values=True).get("page", ["0"])
    if len(pages) != 1 or not pages[0].isascii() or not pages[0].isdigit():
        raise ValueError("Некорректный номер страницы поиска.")
    return host, parts.path.rstrip("/"), int(pages[0])


def read_search_cards(cards):
    """Читает карточки одной страницы; None означает сбой браузера."""
    vacancies = []
    for card in cards:
        try:
            title = card.text.strip()
            raw_link = card.get_attribute("href")
            if not title or not raw_link:
                continue

            # Очистка ссылки нужна только для вакансий hh.
            vacancy_id, clean_link = utils.parse_vacancy_link(raw_link)
            if vacancy_id and title:
                vacancies.append({
                    "id": vacancy_id,
                    "title": title,
                    "link": clean_link,
                })
        except (NoSuchElementException, StaleElementReferenceException, ValueError) as error:
            print(f"Пропускаю карточку: {error}")
            continue
        except (WebDriverException, HTTPError) as error:
            print(f"Не удалось прочитать карточку: {error}")
            print("Сбор ссылок остановлен. Проверьте Chrome.")
            return None
    return vacancies


def check_search_page(driver, expected_page):
    """Сверяет URL и активную страницу выдачи, чтобы не читать прежний DOM."""
    if get_search_page(driver.current_url) != expected_page:
        raise ValueError("Переход на ожидаемую страницу не подтверждён.")

    pages = driver.find_elements(By.CSS_SELECTOR, 'a[data-qa="pager-page"]')
    pages = [page for page in pages if page.is_displayed()]
    # У единственной первой страницы пагинации может не быть.
    if not pages and expected_page[2] == 0:
        return
    active = [page for page in pages if page.get_attribute("aria-current") == "true"]
    if (
        len(active) != 1
        or get_search_page(active[0].get_attribute("href") or "") != expected_page
    ):
        raise ValueError(f"Содержимое страницы {expected_page[2] + 1} ещё не подтверждено.")


def read_search_page(driver, expected_page):
    """Проверяет адрес и читает карточки открытой страницы поиска."""
    browser.check_authorization(driver)
    driver.execute_script("window.scrollBy(0, 1500);")
    utils.human_delay(config.DELAY_SEARCH_SCROLL)
    browser.check_authorization(driver)

    # Проверяем и URL, и выделенный номер после прокрутки и паузы.
    check_search_page(driver, expected_page)

    cards = driver.find_elements(
        By.CSS_SELECTOR,
        'a[data-qa="serp-item__title"]',
    )
    print(f"🔍 Найдено карточек на текущей странице: {len(cards)}")
    vacancies = read_search_cards(cards)
    check_search_page(driver, expected_page)
    return vacancies


def find_next_search_button(driver):
    """Ищет «Дальше» или номерную ссылку строго на соседнюю страницу."""
    current = get_search_page(driver.current_url)
    expected = (*current[:2], current[2] + 1)
    selectors = ('a[data-qa="pager-next"]', 'a[data-qa="pager-page"]')
    for selector in selectors:
        for button in driver.find_elements(By.CSS_SELECTOR, selector):
            if not button.is_displayed() or not button.is_enabled():
                continue
            # Используем адрес существующей ссылки, сохраняя её параметры поиска.
            if get_search_page(button.get_attribute("href") or "") == expected:
                return button
    return None


def go_to_next_search_page(driver):
    """Прокручивает к «Дальше», повторно проверяет кнопку и нажимает один раз."""
    next_button = find_next_search_button(driver)
    if next_button is None:
        print("Следующая страница не найдена. Сбор ссылок завершён.")
        return None

    next_page = get_search_page(next_button.get_attribute("href") or "")
    current_page = get_search_page(driver.current_url)
    # Проверяем домен, путь и последовательный номер страницы.
    if next_page[:2] != current_page[:2] or next_page[2] != current_page[2] + 1:
        raise ValueError("Кнопка «Дальше» ведёт не на следующую страницу.")

    print("Перехожу к следующей странице...")
    # Selenium сначала покажет кнопку; прокрутка вниз на 250 px поднимет её над нижней панелью.
    origin = ScrollOrigin.from_element(next_button)
    ActionChains(driver).scroll_from_origin(origin, 0, 250).perform()
    utils.human_delay(config.DELAY_BEFORE_NEXT_PAGE)
    stop_control.check()
    browser.check_authorization(driver)

    # После прокрутки hh может перерисовать кнопку: заново читаем элемент и его адрес.
    next_button = find_next_search_button(driver)
    if next_button is None or not next_button.is_enabled():
        raise ValueError("Кнопка «Дальше» недоступна для нажатия.")
    if (
        get_search_page(driver.current_url) != current_page
        or get_search_page(next_button.get_attribute("href") or "") != next_page
    ):
        raise ValueError("Страница поиска или адрес «Дальше» изменились. Переход отменён.")
    try:
        # Обычный клик сохраняет проверку перекрытия; принудительный клик не используется.
        next_button.click()
    except ElementClickInterceptedException:
        raise ValueError(
            "Кнопка «Дальше» перекрыта другим элементом. "
            "Проверьте окна поверх выдачи в Chrome."
        ) from None
    except StaleElementReferenceException:
        raise ValueError(
            "Кнопка «Дальше» изменилась перед кликом. "
            "Повторите запуск с текущей страницы."
        ) from None

    utils.human_delay(config.DELAY_NEXT_PAGE_LOAD)
    return next_page


def collect_search_links(driver, search_url):
    """Собирает вакансии из поиска; при ошибке возвращает None."""
    print("🚀 Открываю выбранный поиск hh.")

    try:
        expected_page = get_search_page(search_url)
        browser.check_authorization(driver)
        driver.get(search_url)
    except (PermissionError, ValueError, WebDriverException, HTTPError) as error:
        print(f"Не удалось открыть поиск: {error}")
        return None

    utils.human_delay(config.DELAY_SEARCH_LOAD)
    vacancies = []
    seen_ids = set()

    for page in range(config.PAGES_TO_SCRAPE):
        stop_control.check()
        print(
            f"\n📄 --- Сканирую страницу поиска "
            f"{page + 1} из {config.PAGES_TO_SCRAPE} ---"
        )

        try:
            page_vacancies = read_search_page(driver, expected_page)
        except (PermissionError, ValueError, WebDriverException, HTTPError) as error:
            print(f"Не удалось прочитать выдачу: {error}")
            return None

        if page_vacancies is None:
            return None

        # Ноль карточек может означать ошибку загрузки, а не пустой поиск.
        if not page_vacancies:
            print("Выдача не подтверждена: пригодные карточки не найдены.")
            print("Проверьте страницу поиска в Chrome.")
            return None

        page_ids = {item["id"] for item in page_vacancies}
        if not page_ids - seen_ids:
            print("Выдача не обновилась: все найденные ID уже встречались.")
            print("Сбор остановлен. Проверьте переход между страницами.")
            return None

        vacancies.extend(page_vacancies)
        seen_ids.update(page_ids)

        # На последней запрошенной странице переход не нужен.
        if page == config.PAGES_TO_SCRAPE - 1:
            continue

        try:
            next_page = go_to_next_search_page(driver)

        except (PermissionError, ValueError, WebDriverException, HTTPError) as error:
            # Ошибка перехода прерывает сбор целиком.
            print(f"Ошибка перехода на следующую страницу: {error}")
            print("Запуск остановлен.")
            return None
        # Кнопки больше нет: возвращаем уже собранные вакансии.
        if next_page is None:
            break
        expected_page = next_page

    return vacancies
