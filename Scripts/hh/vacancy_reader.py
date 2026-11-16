# vacancy_reader.py

from selenium.webdriver.common.by import By

from hh import browser
from hh import captcha
from core import config
from core import utils
from core.vacancy import normalize_vacancy


def read_company(driver):
    """Возвращает название компании и ссылку на её страницу."""
    elements = driver.find_elements(
        By.CSS_SELECTOR,
        'a[data-qa="vacancy-company-name"]',
    )

    if not elements:
        print("    Компания не найдена.")
        return "", ""

    company = elements[0]
    company_name = company.text.strip()
    company_link = company.get_attribute("href") or ""

    # Убираем параметры и фрагмент из ссылки.
    company_link = company_link.split("?")[0].split("#")[0]

    return company_name, company_link


def read_salary(driver):
    """Возвращает зарплату текстом или пустую строку."""
    elements = driver.find_elements(
        By.CSS_SELECTOR,
        '[data-qa="vacancy-salary"]',
    )

    if not elements:
        print("    Зарплата не указана.")
        return ""

    # Сохраняем валюту, период и пометку о налогах.
    return elements[0].text.strip()


def read_vacancy(driver, item):
    """Открывает вакансию и возвращает её данные."""

    # Браузер уже подключён в скрипте, который вызвал эту функцию.
    captcha.stop_if_visible(driver)
    driver.get(item["link"])
    utils.human_delay(config.DELAY_VACANCY_LOAD)
    captcha.stop_if_visible(driver)

    driver.execute_script("window.scrollBy(0, 1000);")
    utils.human_delay(config.DELAY_VACANCY_SCROLL)

    # Проверяем после пауз: форма входа могла появиться с задержкой.
    browser.check_authorization(driver)

    # Проверяем адрес после загрузки: браузер мог перейти на другую страницу.
    actual_id, _ = utils.parse_vacancy_link(driver.current_url)
    if actual_id != item["id"]:
        raise ValueError(
            f"Ожидалась вакансия {item['id']}, открылась {actual_id}."
        )

    # Поиск передаёт название из карточки, а режим ссылок — только ID и адрес.
    # Если названия нет, читаем его с самой страницы вакансии.
    title = item.get("title", "").strip()
    if not title:
        title = driver.find_element(
            By.CSS_SELECTOR,
            '[data-qa="vacancy-title"]',
        ).text.strip()

    # .text возвращает обычный текст без HTML-разметки.
    # Ошибку поиска элемента обработает вызывающий скрипт.
    description = driver.find_element(
        By.CSS_SELECTOR,
        '[data-qa="vacancy-description"]',
    ).text.strip()

    # Не сохраняем сообщение об ошибке вместо описания и не ставим new.
    if not title or not description:
        raise ValueError("Не удалось прочитать название или описание вакансии.")

    # Отсутствие необязательных данных допустимо: функции вернут пустые строки.
    company_name, company_link = read_company(driver)
    salary = read_salary(driver)

    # Статус задаёт вызывающий скрипт после успешного чтения.
    return normalize_vacancy({
        "ID": item["id"],
        "Компания": company_name,
        "Компания ссылка": company_link,
        "Заголовок": title,
        "Зарплата": salary,
        "Описание": description,
        "Ссылка": item["link"],
    })
