# application_sender.py

from hh import application_dialog
from hh import application_result
from tables import application_sheet
from hh import browser
from hh import response_reader
from core import utils


def send_application(driver, sheet, row_number, row, item):
    """Выполняет шаги отклика; анкета сразу возвращается на ручную обработку."""
    application_sheet.require_ready_application(row)
    # За время загрузки вакансии ссылку, письмо или статус могли изменить.
    application_sheet.check_application_row(sheet, row_number, row)
    if not application_dialog.open_application(driver):
        return "form", "Анкета: " + driver.current_url

    if not application_dialog.fill_letter(driver, row["Сопроводительное"]):
        return "form", "Анкета: " + driver.current_url

    # Отправляем именно то письмо, которое пользователь оставил в таблице.
    application_sheet.check_application_row(sheet, row_number, row)
    previous_handles = set(driver.window_handles)
    if not application_dialog.submit_application(driver, row["Сопроводительное"]):
        return "form", "Анкета: " + driver.current_url

    # После клика только ждём результат: повторно вакансию не открываем.
    status = application_result.wait_for_result(driver, item, previous_handles)
    comment = "Анкета: " + driver.current_url if status == "form" else None
    return status, comment


def process_application(driver, sheet, row_number, row, item):
    """Проверяет одну вакансию, отправляет письмо и сохраняет статус."""
    # Неготовую строку отклоняем до открытия вакансии.
    application_sheet.require_ready_application(row)

    if (item["id"], item["link"]) != utils.parse_vacancy_link(row["Ссылка"]):
        raise ValueError("Данные обработчика не соответствуют ссылке строки.")

    # При каждом запуске сначала проверяем, не отправлен ли отклик раньше.
    result = response_reader.read_response(driver, item)
    if result["response"] is not None or result["availability"] != "active":
        status = response_reader.get_response_status(result)
        application_sheet.update_application_row(
            sheet, row_number, row, status,
        )
        print(f"Строка {row_number}: на hh уже установлен статус {status}.")
        return "updated"

    # До подтверждённого результата сохраняем исходный статус строки.
    original_window = driver.current_window_handle
    original_handles = set(driver.window_handles)

    status, comment = send_application(
        driver, sheet, row_number, row, item,
    )
    application_sheet.update_application_row(
        sheet, row_number, row, status, comment,
    )
    print(f"Строка {row_number}: статус {status}.")

    # При неизвестном результате вкладки остаются открыты для проверки.
    browser.close_new_tabs(driver, original_handles, original_window)
    # Только подтверждённая новая отправка расходует лимит откликов.
    return "form" if status == "form" else "sent"
