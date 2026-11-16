"""Понятные шаги одного отклика; все клики проходят одну проверку цели."""

import time

from tables import application_sheet
from core import config
from core import stop_control


def click_element(controls, screen, name, dialog=False):
    """False — анкета; при исчезновении цели клик отменяется."""
    screen.take()
    if screen.guard() == "form":
        return False
    if dialog:
        screen.require_dialog()
    box = screen.find(name, dialog=dialog, unique=name != "apply")
    if box is None:
        raise RuntimeError(f"Не найден элемент «{name}». Клика не было.")
    point = controls.move_to(box)
    if not screen.confirm_target(name, point, box, dialog=dialog):
        return False
    controls.click_at(point)
    return True


def letter_text(row):
    return row["Сопроводительное"].replace("\r\n", "\n").replace("\r", "\n")


def fill_open_dialog(controls, screen, item, row):
    """Заполняет открытое окно; False оставляет анкету на ручную обработку."""
    controls.require_vacancy(item)
    if not screen.check_letter_dialog():
        return False
    if screen.find("letter", dialog=True) is None:
        if not click_element(controls, screen, "add_letter", dialog=True):
            return False
        name, _ = screen.wait(("letter",), config.APPLICATION_OPEN_TIMEOUT, dialog=True)
        if name == "form":
            return False
    if not click_element(controls, screen, "letter", dialog=True):
        return False
    return controls.type_letter(letter_text(row), check_page=screen.check_letter_dialog)


def wait_for_outcome(controls, screen, item):
    controls.delay(config.DELAY_APPLICATION_RESULT)
    deadline = time.monotonic() + config.APPLICATION_RESULT_TIMEOUT
    while True:
        screen.take()
        if screen.guard() == "form":
            return "form"
        status = screen.status()
        if status:
            controls.require_vacancy(item)
            return status
        if time.monotonic() >= deadline:
            raise RuntimeError("Результат не подтверждён. Повторного клика не будет; проверьте hh.")
        stop_control.pause(0.5)


def save_status(sheet, number, row, status, controls):
    comment = "Анкета: " + controls.read_url() if status == "form" else None
    application_sheet.update_application_row(sheet, number, row, status, comment)


def read_page_status(controls, screen, item):
    """Распознанную анкету возвращает без дополнительных действий в её полях."""
    screen.take()
    if screen.guard() == "form":
        return "form"
    controls.require_vacancy(item)
    screen.take()
    if screen.guard() == "form":
        return "form"
    return screen.status()


def send_one(sheet, number, row, item, controls, screen):
    controls.open_vacancy(item)
    controls.delay(config.DELAY_VACANCY_LOAD)
    status = read_page_status(controls, screen, item)
    if status:
        save_status(sheet, number, row, status, controls)
        return status
    controls.delay(config.DELAY_BEFORE_APPLICATION_CLICK)
    status = read_page_status(controls, screen, item)
    if status:
        save_status(sheet, number, row, status, controls)
        return status
    if not click_element(controls, screen, "apply"):
        save_status(sheet, number, row, "form", controls)
        return "form"
    controls.delay(config.DELAY_APPLICATION_OPEN)
    name, _ = screen.wait(("dialog", "wait", "delivered"), config.APPLICATION_OPEN_TIMEOUT)
    if name == "form":
        save_status(sheet, number, row, "form", controls)
        return "form"
    if name in ("wait", "delivered"):
        controls.require_vacancy(item)
        save_status(sheet, number, row, "wait", controls)
        raise RuntimeError("hh подтвердил отклик без окна письма. Статус wait сохранён; проверьте письмо вручную.")
    if not fill_open_dialog(controls, screen, item, row):
        save_status(sheet, number, row, "form", controls)
        return "form"
    controls.delay(config.DELAY_BEFORE_APPLICATION_SEND)
    application_sheet.check_application_row(sheet, number, row)
    controls.require_vacancy(item)
    if not screen.check_letter_dialog():
        save_status(sheet, number, row, "form", controls)
        return "form"
    # Проверяем фактический текст ещё раз, после паузы и чтения таблицы.
    # При потере фокуса копируется другой текст и отправка отменяется.
    controls.verify_letter(letter_text(row))
    if not click_element(controls, screen, "submit", dialog=True):
        save_status(sheet, number, row, "form", controls)
        return "form"
    status = wait_for_outcome(controls, screen, item)
    save_status(sheet, number, row, status, controls)
    return "sent" if status == "wait" else status
