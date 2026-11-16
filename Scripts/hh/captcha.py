"""Останавливает сценарии hh при появлении проверки пользователя."""

from selenium.webdriver.common.by import By

from core import config
from core.settings_store import resolve_path


CAPTCHA_INPUT = 'input[data-qa="account-captcha-input"]'
DUCK_FILE = resolve_path(config.VALUES["sound_file"])


def is_visible(driver):
    """Проверяет именно видимое поле капчи, а не скрытую разметку страницы."""
    fields = driver.find_elements(By.CSS_SELECTOR, CAPTCHA_INPUT)
    return any(field.is_displayed() for field in fields)


def play_until_cleared(driver):
    """Сохраняет прежний способ остановки и звучания при капче Selenium."""
    from core.sound_alarm import play_until_cleared as play_sound
    return play_sound(lambda: is_visible(driver), DUCK_FILE)

def stop_if_visible(driver):
    """Даёт пройти капчу вручную и затем останавливает текущий запуск."""
    if not is_visible(driver):
        return

    print("Обнаружена капча hh. Пройдите её в Chrome; звук остановится сам.")
    play_until_cleared(driver)
    raise PermissionError(
        "Обнаружена капча hh. Запуск остановлен; повторите его после проверки."
    )
