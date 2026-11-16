# application_letter.py

from selenium.webdriver.common.by import By

from hh import application_form
from hh import captcha
from core import config
from core import utils


def open_letter_field(driver, dialog):
    """Раскрывает поле письма; False означает анкету."""
    if application_form.is_manual_form(driver):
        return False

    fields = dialog.find_elements(
        By.CSS_SELECTOR,
        'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
    )
    if any(field.is_displayed() for field in fields):
        return True

    buttons = [
        button
        for button in dialog.find_elements(
            By.CSS_SELECTOR, 'button[data-qa="add-cover-letter"]',
        )
        if button.is_displayed()
        and button.is_enabled()
        and button.get_attribute("type") == "button"
    ]
    if len(buttons) != 1:
        raise RuntimeError("Кнопка добавления письма не найдена или неоднозначна.")

    print("Раскрываю поле сопроводительного письма.")
    buttons[0].click()
    return True


def type_letter(driver, field, text):
    """Вводит письмо частями, сохраняя пробелы и переносы."""
    chunk_size = 20
    print("Ввожу сопроводительное письмо частями.")
    for start in range(0, len(text), chunk_size):
        captcha.stop_if_visible(driver)
        field.send_keys(text[start:start + chunk_size])
        if start + chunk_size < len(text):
            utils.human_delay(config.DELAY_LETTER_CHUNK, announce=False)
