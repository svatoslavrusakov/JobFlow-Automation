# application_dialog.py

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from hh import application_form
from hh import application_letter
from hh import browser
from hh import captcha
from core import config
from core import utils


def visible_elements(scope, selector):
    return [
        element for element in scope.find_elements(By.CSS_SELECTOR, selector)
        if element.is_displayed()
    ]


def get_application_dialog(driver):
    """Находит обычное окно отклика с уже выбранным резюме."""
    if application_form.is_manual_form(driver):
        raise RuntimeError("Открыта анкета. Заполнение отменено.")

    dialogs = visible_elements(driver, '[role="dialog"][aria-modal="true"]')
    if len(dialogs) != 1:
        raise RuntimeError("Обычное окно отклика не найдено или неоднозначно.")

    dialog = dialogs[0]
    if not visible_elements(dialog, '[data-qa="resume-title"]'):
        raise RuntimeError("В окне не показано выбранное резюме.")
    return dialog


def get_letter_dialog(driver):
    """Возвращает обычное окно и доступное поле письма."""
    dialog = get_application_dialog(driver)
    letters = visible_elements(
        dialog, 'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
    )
    if len(letters) != 1:
        raise RuntimeError("Не найдено единственное поле сопроводительного.")
    if not letters[0].is_enabled() or letters[0].get_attribute("readonly"):
        raise RuntimeError("Поле письма недоступно для ввода.")
    return dialog, letters[0]


def wait_for_application(driver, previous_handles, require_letter=False):
    """Ждёт обычное окно, доступное поле письма или анкету."""
    timeout = config.APPLICATION_OPEN_TIMEOUT
    target = "поля сопроводительного" if require_letter else "окна отклика"
    print(f"Ожидаю готовность {target}: до {timeout:g} с")

    def ready(current_driver):
        browser.switch_to_new_tab(current_driver, previous_handles)
        try:
            # Если вместо окна появилась капча, останавливаемся со звуком.
            captcha.stop_if_visible(current_driver)
            if application_form.is_manual_form(current_driver):
                return "form"
            dialog = get_application_dialog(current_driver)
            if not require_letter:
                # Свёрнутое письмо тоже является обычным сценарием отклика.
                buttons = visible_elements(
                    dialog, 'button[data-qa="add-cover-letter"]',
                )
                if (
                    len(buttons) == 1
                    and buttons[0].is_enabled()
                    and buttons[0].get_attribute("type") == "button"
                ):
                    return "letter"
            get_letter_dialog(current_driver)
        except (RuntimeError, StaleElementReferenceException):
            return False
        return "letter"

    screen = WebDriverWait(driver, timeout).until(
        ready,
        message=f"Не удалось дождаться {target}. Проверьте страницу hh.",
    )
    if screen == "letter":
        print("Поле письма готово." if require_letter else "Окно отклика готово.")
    return screen == "letter"


def open_application(driver):
    """Нажимает первый отклик один раз; False означает ручную форму."""
    if application_form.is_manual_form(driver):
        return False
    buttons = [
        button for button in visible_elements(
            driver, 'a[data-qa="vacancy-response-link-top"]',
        )
        if button.is_enabled()
    ]
    if not buttons:
        raise RuntimeError("Кнопка первого отклика не найдена.")

    # Прокручиваем к кнопке, если она вне экрана, и выдерживаем паузу.
    ActionChains(driver).scroll_to_element(buttons[0]).perform()
    utils.human_delay(config.DELAY_BEFORE_APPLICATION_CLICK)
    captcha.stop_if_visible(driver)
    previous_handles = set(driver.window_handles)
    buttons[0].click()
    utils.human_delay(config.DELAY_APPLICATION_OPEN)
    return wait_for_application(driver, previous_handles)


def fill_letter(driver, text):
    """Вставляет письмо только в подтверждённое обычное окно."""
    if application_form.is_manual_form(driver):
        return False
    if not text.strip():
        raise ValueError("Сопроводительное письмо пустое.")

    dialog = get_application_dialog(driver)
    previous_handles = set(driver.window_handles)
    if not application_letter.open_letter_field(driver, dialog):
        return False
    if not wait_for_application(driver, previous_handles, require_letter=True):
        return False

    _, letter = get_letter_dialog(driver)
    letter.clear()
    application_letter.type_letter(driver, letter, text)
    utils.human_delay(config.DELAY_BEFORE_APPLICATION_SEND)
    return not application_form.is_manual_form(driver)


def submit_application(driver, text):
    """Проверяет текст и выполняет один финальный клик."""
    captcha.stop_if_visible(driver)
    if application_form.is_manual_form(driver):
        return False

    dialog, letter = get_letter_dialog(driver)
    expected = text.replace("\r\n", "\n")
    actual = (letter.get_attribute("value") or "").replace("\r\n", "\n")
    if actual != expected:
        raise RuntimeError("Введённое письмо не совпадает с таблицей.")

    buttons = visible_elements(
        dialog, 'button[data-qa="vacancy-response-submit-popup"]',
    )
    if len(buttons) != 1 or not buttons[0].is_enabled():
        raise RuntimeError("Кнопка отправки недоступна.")

    buttons[0].click()
    # Клик не подтверждает доставку. Результат отдельно ждёт application_result.
    return True
