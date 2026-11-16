# application_form.py

from urllib.parse import urlsplit

from selenium.webdriver.common.by import By

from hh import browser
from hh import captcha
from core import utils


def has_questionnaire(driver):
    """Распознаёт анкету без изменений страницы."""
    forms = driver.find_elements(
        By.CSS_SELECTOR, 'form[name="vacancy_response"]',
    )
    for form in forms:
        if not form.is_displayed():
            continue

        # Скрытый флаг обязательного теста из примера разметки.
        if form.find_elements(
            By.CSS_SELECTOR, 'input[name="testRequired"][value="true"]',
        ):
            return True

        questions = form.find_elements(
            By.CSS_SELECTOR,
            '[data-qa="employer-asking-for-test"], '
            '[data-qa="task-body"], [data-qa="task-question"], '
            'textarea[name^="task_"]',
        )
        if any(question.is_displayed() for question in questions):
            return True
    return False


def is_manual_form(driver):
    """Проверяет анкету, внешний сайт и дополнительные поля именно окна отклика."""
    # Поле капчи нельзя принимать за вопрос анкеты и записывать статус form.
    captcha.stop_if_visible(driver)
    if has_questionnaire(driver):
        return True

    parts = urlsplit(driver.current_url)
    host = parts.hostname or ""
    if parts.scheme in ("http", "https") and not utils.is_hh_host(host):
        return True

    if browser.login_form_visible(driver):
        raise PermissionError("hh требует входа. Проверьте авторизацию.")

    dialogs = driver.find_elements(
        By.CSS_SELECTOR, '[role="dialog"][aria-modal="true"]',
    )
    for dialog in dialogs:
        if not dialog.is_displayed():
            continue
        # Город и другие служебные окна не относятся к анкете работодателя.
        anchors = dialog.find_elements(
            By.CSS_SELECTOR,
            '[data-qa="resume-title"], [data-qa="vacancy-response-submit-popup"]',
        )
        if not any(anchor.is_displayed() for anchor in anchors):
            continue
        controls = dialog.find_elements(
            By.CSS_SELECTOR,
            'input, textarea, select, [contenteditable="true"], '
            '[role="checkbox"], [role="radio"], [role="textbox"], '
            '[role="combobox"]',
        )
        for control in controls:
            if not control.is_displayed():
                continue
            if control.get_attribute("data-qa") != "vacancy-response-popup-form-letter-input":
                return True
    return False
