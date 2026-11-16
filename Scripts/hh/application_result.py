"""Ожидает результат отправки на текущей странице, без повторных кликов."""

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait

from hh import application_form
from hh import browser
from core import config
from hh import response_reader
from core import utils


def wait_for_result(driver, item, previous_handles):
    """Возвращает подтверждённый статус или form; неизвестный экран останавливает запуск."""
    # Сохраняем прежнюю паузу после клика; она не заменяет проверку результата.
    utils.human_delay(config.DELAY_APPLICATION_RESULT)
    timeout = config.APPLICATION_RESULT_TIMEOUT
    print(f"Ожидаю подтверждение отклика без перезагрузки: до {timeout:g} с")

    def ready(current_driver):
        # Новая вкладка может появиться с задержкой после финального клика.
        browser.switch_to_new_tab(current_driver, previous_handles)
        # Капча и вход останавливают работу внутри этой общей проверки.
        # Служебные окна hh не считаются анкетами работодателя.
        if application_form.is_manual_form(current_driver):
            return "form"
        result = response_reader.read_current_response(current_driver, item)
        if result["response"] in ("wait", "reject", "invite"):
            return response_reader.get_response_status(result)
        return False

    try:
        status = WebDriverWait(
            driver, timeout,
            ignored_exceptions=(NoSuchElementException, StaleElementReferenceException),
        ).until(ready)
    except TimeoutException:
        # Повторного клика и автоматической перезагрузки здесь нет.
        raise RuntimeError(
            "Отправка не подтверждена. Проверьте отклик на hh."
        ) from None
    print(f"Результат отклика распознан: {status}.")
    return status
