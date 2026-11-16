# sheets.py

from datetime import datetime

import gspread
from gspread.utils import rowcol_to_a1
from core import config
from tables import google_connection
from tables import table_columns


# Дата добавления необязательна для старых листов.
ADDED_AT_HEADER = "Дата и время добавления"

# Обязательные колонки; порядок на листе может быть любым.
REQUIRED_HEADERS = (
    "ID",
    "Компания",
    "Компания ссылка",
    "Заголовок",
    "Зарплата",
    "Описание",
    "Ссылка",
    "Статус",
)


def read_headers(sheet, required_headers=REQUIRED_HEADERS):
    """Читает и проверяет заголовки первой строки."""
    # Примечания связывают отображаемые названия с прежними ключами программы.
    headers = table_columns.canonical_headers(sheet)

    # Пропуски сохраняют позиции колонок; проверяем дубли и обязательные поля.
    if not any(headers):
        raise ValueError(
            "В первой строке нужны заголовки колонок."
        )

    duplicates = sorted({header for header in headers if header and headers.count(header) > 1})
    if duplicates:
        raise ValueError(f"Повторяются заголовки: {', '.join(duplicates)}")

    missing = [header for header in required_headers if header not in headers]
    if missing:
        raise ValueError(f"Не найдены обязательные колонки: {', '.join(missing)}")

    return headers


def read_current_row(
    sheet, row_number, headers,
    date_time_render_option="SERIAL_NUMBER",
):
    """Читает строку в словарь по уже проверенным заголовкам."""
    # FORMULA позволяет сохранить формулы, включая формулы с пустым результатом.
    values = sheet.row_values(
        row_number,
        value_render_option="FORMULA",
        date_time_render_option=date_time_render_option,
    )

    # Google не возвращает пустые ячейки в конце строки.
    return {
        header: str(values[index]) if index < len(values) else ""
        for index, header in enumerate(headers) if header
    }


def init_google_sheet():
    """Подключается к выбранному листу."""
    try:
        sheet = google_connection.request_with_retry(
            google_connection.open_worksheet, worksheet=config.WORKSHEET_NAME,
        )

        # Каждый сценарий сам загрузит нужные ему данные.
        print(f"Подключён лист «{sheet.title}».")
        return sheet

    except gspread.WorksheetNotFound:
        print(
            f"Лист «{config.WORKSHEET_NAME}» не найден. "
            "Проверьте название листа в окне или в настройках."
        )
    except Exception as error:
        print(f"Ошибка подключения к Google Таблице: {error}")

    return None


def prepare_vacancy_row(vacancy, headers):
    """Проверяет поля и собирает строку; запросов к Google здесь нет."""
    missing = [header for header in REQUIRED_HEADERS if header not in vacancy]
    if missing:
        raise ValueError(f"В данных вакансии отсутствуют поля: {', '.join(missing)}")
    unknown = [header for header in vacancy if header not in headers]
    if unknown:
        raise ValueError(f"Для полей вакансии нет колонок: {', '.join(unknown)}")

    row_data = [vacancy.get(header, "") for header in headers]
    # Неполная карточка остаётся без даты; готовая вакансия получает дату добавления.
    if ADDED_AT_HEADER in headers and vacancy["Статус"] in ("new", "done", "thinking"):
        row_data[headers.index(ADDED_AT_HEADER)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return row_data


def save_vacancies(sheet, existing_ids, vacancies, headers=None):
    """Добавляет одну партию; импорт передаёт уже проверенную шапку."""
    if not vacancies:
        return
    if headers is None:
        headers = google_connection.request_with_retry(read_headers, sheet)
    rows = [prepare_vacancy_row(vacancy, headers) for vacancy in vacancies]
    # RAW сохраняет обычный текст; INSERT_ROWS сдвигает строки под местом вставки.
    response = google_connection.request_with_retry(
        sheet.append_rows, rows,
        value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1",
    )
    # Кэш изменяем только после подтверждённого ответа Google.
    vacancy_ids = [str(vacancy["ID"]).strip() for vacancy in vacancies]
    existing_ids.update(vacancy_ids)
    written_range = response.get("updates", {}).get("updatedRange", "")
    location = f", {written_range}" if written_range else ""
    details = f"ID: {vacancy_ids[0]}" if len(vacancies) == 1 else f"строк: {len(vacancies)}"
    print(f"    Записано в Google Таблицу ({details}{location})")


def save_vacancy(sheet, existing_ids, vacancy):
    """Одиночная запись использует ту же подготовку и отправку, что и партия."""
    save_vacancies(sheet, existing_ids, [vacancy])


def read_vacancy_rows(
    sheet, fields=("ID", "Ссылка", "Статус"), required_headers=REQUIRED_HEADERS,
    headers=None,
):
    """Читает выбранные колонки, сохраняя исходные номера строк."""
    # Можно передать шапку, уже проверенную в рамках этой загрузки очереди.
    # Длительные обработчики перечитывают шапку перед записью; быстрый импорт использует снимок.
    if headers is None:
        headers = read_headers(sheet, required_headers=required_headers)

    missing = [field for field in fields if field not in headers]
    if missing:
        raise ValueError("Не найдены колонки для чтения: " + ", ".join(missing))

    # В листе может быть только строка заголовков.
    if sheet.row_count < 2:
        return []
    ranges = []

    for field in fields:
        column_number = headers.index(field) + 1

        # Из адреса вроде C1 получаем обозначение колонки C.
        column_letter = rowcol_to_a1(1, column_number)[:-1]

        # Например, C2:C — колонка C начиная со второй строки.
        ranges.append(f"{column_letter}2:{column_letter}")

    # Нужные колонки получаем одним запросом, без описаний и писем.
    results = sheet.batch_get(ranges, major_dimension="COLUMNS")

    # В каждом результате находится один столбец либо пустой список.
    columns = [result[0] if result else [] for result in results]

    # Колонки могут заканчиваться на разных строках.
    row_count = max((len(column) for column in columns), default=0)
    rows = []

    for offset in range(row_count):
        row = {
            field: str(column[offset]) if offset < len(column) else ""
            for field, column in zip(fields, columns)
        }

        # Пустые промежуточные строки сохраняем, чтобы номера не сместились.
        rows.append((offset + 2, row))

    return rows


def fill_vacancy_row(sheet, row_number, original_link, vacancy):
    """Дополняет исходную строку, сохраняя заполненные ячейки."""
    # Перед записью заново определяем колонки и читаем текущие значения.
    headers = read_headers(sheet)

    # Даже формулу с пустым результатом считаем заполненной ячейкой.
    current = read_current_row(sheet, row_number, headers)

    # За время чтения страницы пользователь мог изменить ссылку или статус.
    # В таком случае оставляем строку для отдельной проверки.
    if current["Ссылка"].strip() != original_link.strip():
        raise ValueError("Ссылка в строке изменилась. Запись пропущена.")

    if current["Статус"].strip():
        raise ValueError("Статус строки уже заполнен. Запись пропущена.")

    if current["ID"].strip() not in ("", vacancy["ID"]):
        raise ValueError("ID в строке не совпадает с ID вакансии.")

    updates = []

    for header, value in vacancy.items():
        # Не записываем пустые необязательные данные.
        if not value:
            continue

        # Ссылку очищаем от параметров; остальные непустые ячейки сохраняем.
        # Комментарии, письма и результаты ИИ сюда вообще не передаются.
        if header != "Ссылка" and current[header].strip():
            continue

        # Переводим номер строки и колонки в адрес вроде D5.
        column_number = headers.index(header) + 1
        updates.append({
            "range": rowcol_to_a1(row_number, column_number),
            "values": [[value]],
        })

    # Дату записываем вместе с данными, не заменяя ручное значение или формулу.
    if updates and ADDED_AT_HEADER in headers and not current[ADDED_AT_HEADER].strip():
        updates.append({
            "range": rowcol_to_a1(row_number, headers.index(ADDED_AT_HEADER) + 1),
            "values": [[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]],
        })

    if updates:
        # Один запрос обновляет только выбранные ячейки, без добавления строки.
        # RAW сохраняет текст как есть, без распознавания формул и дат.
        sheet.batch_update(updates, value_input_option="RAW")


def read_row_fields(sheet, numbers, headers, fields):
    """Читает только нужные ячейки выбранных строк, сохраняя формулы."""
    numbers = list(dict.fromkeys(numbers))
    result = {number: dict.fromkeys(fields, "") for number in numbers}
    columns = {headers.index(field): field for field in fields if field in headers}
    if not numbers or not columns:
        return result
    filters = [
        {"gridRange": {
            "sheetId": sheet.id, "startRowIndex": number - 1, "endRowIndex": number,
            "startColumnIndex": column, "endColumnIndex": column + 1,
        }}
        for number in numbers for column in columns
    ]
    # Этот POST — операция чтения. Тело запроса позволяет не зависеть
    # от длины названия листа и не загружать промежуточные строки.
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet.spreadsheet_id}/values:batchGetByDataFilter"
    data = sheet.client.request("post", url, json={
        "dataFilters": filters, "majorDimension": "ROWS",
        "valueRenderOption": "FORMULA", "dateTimeRenderOption": "FORMATTED_STRING",
    }).json()
    for matched in data.get("valueRanges", []):
        cells = matched.get("valueRange", {}).get("values", [])
        # Запрашивалась одна ячейка: неожиданный ответ не показываем как верный.
        if len(cells) > 1 or (cells and len(cells[0]) > 1):
            raise ValueError("Google вернул более одной ячейки на фильтр.")
        value = str(cells[0][0]) if cells and cells[0] else ""
        if not matched.get("dataFilters"):
            raise ValueError("Google не вернул адреса прочитанных ячеек.")
        # Порядок результатов не используется: адрес приходит вместе с фильтром.
        for item in matched["dataFilters"]:
            area = item.get("gridRange", {})
            number = area.get("startRowIndex", -1) + 1
            column = area.get("startColumnIndex", 0)
            if (area.get("sheetId") != sheet.id or number not in result or column not in columns
                    or area.get("endRowIndex") != number or area.get("endColumnIndex") != column + 1):
                raise ValueError("Google вернул неожиданный диапазон ячеек.")
            result[number][columns[column]] = value
    return result
