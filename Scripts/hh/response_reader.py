# response_reader.py

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from hh import browser
from hh import captcha
from core import config
from core import utils


RESPONSE_STATUSES = {
    "вы откликнулись": "wait",
    "вам отказали": "reject",
    "вас пригласили": "invite",
    # В предоставленном HTML последняя c в «Ваc» латинская.
    "ваc пригласили": "invite",
}


def read_response_status(driver):
    """Читает видимый ответ по текущей вакансии; неизвестный ответ — None."""
    responses = set()
    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        'button[data-qa="vacancy-response-link-top-again"]',
    )

    for button in buttons:
        # Кнопка служит ориентиром; видимость проверяем у самого ярлыка.
        # Статус находится рядом с блоком действий, а не внутри кнопки.
        # У дублирующей кнопки в нижней панели такого статуса нет.
        scopes = button.find_elements(
            By.XPATH,
            "./ancestor::div["
            "contains(concat(' ', normalize-space(@class), ' '), ' noprint ')"
            "][1]/parent::div",
        )
        for scope in scopes:
            labels = scope.find_elements(
                By.CSS_SELECTOR,
                '[class*="card-content--"] > div',
            )
            for label in labels:
                if not label.is_displayed():
                    continue

                text = " ".join(label.text.split()).casefold()
                response = RESPONSE_STATUSES.get(text)
                if response is not None:
                    responses.add(response)

    if len(responses) > 1:
        raise ValueError("На странице найдены противоречивые ответы работодателя.")

    if responses:
        return next(iter(responses))

    # После отправки hh может сразу показать доставку вместо прежнего ярлыка.
    # Ищем её только в блоке отклика, а не в описании или сообщениях чата.
    blocks = driver.find_elements(By.CSS_SELECTOR, ".vacancy-actions_responded")
    for block in blocks:
        delivered = block.find_elements(
            By.XPATH, ".//*[normalize-space(.)='Резюме доставлено']",
        )
        if any(label.is_displayed() for label in delivered):
            return "wait"
    # Отсутствие подтверждения не означает, что отклик отправлен.
    return None


def get_response_status(result):
    """Переводит распознанное состояние страницы в статус строки."""
    response = result["response"]
    availability = result["availability"]
    if response not in (None, "wait", "reject", "invite"):
        raise ValueError("Получен неизвестный ответ работодателя.")
    if availability not in ("active", "archive", "access_denied"):
        raise ValueError("Состояние вакансии не подтверждено.")

    # Явный ответ работодателя сохраняем даже на архивной странице.
    if response in ("reject", "invite"):
        return response
    if availability == "archive":
        return "archive"
    if availability == "access_denied":
        return "unavailable"
    if response == "wait":
        return "wait"
    raise ValueError("Ответ работодателя не распознан. Строка не изменена.")


def read_response(driver, item):
    """Открывает вакансию и читает ответ, архив или ограничение доступа."""
    # Проверяем текущую вкладку до перехода: капча могла появиться после клика.
    captcha.stop_if_visible(driver)
    driver.get(item["link"])
    utils.human_delay(config.DELAY_VACANCY_LOAD)
    return read_current_response(driver, item)


def read_current_response(driver, item):
    """Читает текущую вакансию без переходов и кликов."""
    captcha.stop_if_visible(driver)
    needs_login = browser.login_form_visible(driver)

    # Для недоступной вакансии тоже сначала подтверждаем ID адреса.
    try:
        actual_id, _ = utils.parse_vacancy_link(driver.current_url)
    except ValueError:
        if needs_login:
            raise PermissionError("hh показывает форму входа. Проверьте авторизацию.") from None
        raise
    if actual_id != item["id"]:
        if needs_login:
            raise PermissionError("hh показывает форму входа и другой адрес. Проверьте авторизацию.")
        raise ValueError(
            f"Ожидалась вакансия {item['id']}, открылась {actual_id}."
        )

    contents = driver.find_elements(
        By.CSS_SELECTOR,
        'main [data-qa="main-content"]',
    )
    for content in contents:
        if not content.is_displayed():
            continue
        text = " ".join(content.text.split()).casefold()
        if "вам недоступна эта вакансия" in text:
            # В этом блоке hh может показывать и форму входа.
            # Она не мешает отметить вакансию недоступной и продолжить очередь.
            return {
                "response": None,
                "availability": "access_denied",
            }

    if needs_login:
        raise PermissionError("hh показывает форму входа. Проверьте авторизацию.")

    titles = driver.find_elements(
        By.CSS_SELECTOR,
        'h1[data-qa="vacancy-title"]',
    )
    if not any(title.is_displayed() and title.text.strip() for title in titles):
        # Ожидание после отправки может повторить чтение, пока DOM обновляется.
        raise NoSuchElementException("Не найден видимый заголовок вакансии.")

    archive_markers = driver.find_elements(
        By.CSS_SELECTOR,
        'h1[data-qa="vacancy-title"] [data-qa="vacancy-title-archived-text"], '
        '[data-qa="vacancy-archive-description"]',
    )
    availability = (
        "archive" if any(marker.is_displayed() for marker in archive_markers)
        else "active"
    )

    return {
        "response": read_response_status(driver),
        "availability": availability,
    }
