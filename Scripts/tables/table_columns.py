"""Читает шапку и редактирует только названия; данные вакансий не удаляет."""

from gspread.utils import rowcol_to_a1

from tables.column_catalog import describe

NOTE_PREFIX = "Auto_hh field: "


def field_from_note(note, fallback):
    for line in note.splitlines():
        if line.startswith(NOTE_PREFIX):
            return line[len(NOTE_PREFIX):].strip() or fallback
    return fallback


def read_columns(sheet, refresh=False):
    """Примечания читаются только из первой строки и кэшируются до изменения шапки."""
    raw = tuple(str(value).strip() for value in sheet.row_values(1))
    cached = getattr(sheet, "_auto_hh_columns", None)
    if not refresh and isinstance(cached, tuple) and cached[0] == raw:
        return [dict(column) for column in cached[1]]
    notes = sheet.get_notes(grid_range="1:1")
    notes = notes[0] if notes else []
    columns = []
    for index in range(max(len(raw), len(notes))):
        name = raw[index] if index < len(raw) else ""
        note = notes[index] if index < len(notes) else ""
        field = field_from_note(note, name)
        owner, required, explanation = describe(field)
        columns.append({
            "number": index + 1, "address": rowcol_to_a1(1, index + 1),
            "name": name, "field": field, "note": note,
            "owner": owner, "required": required, "explanation": explanation,
        })
    sheet._auto_hh_columns = (raw, columns)
    return [dict(column) for column in columns]


def canonical_headers(sheet):
    """Переименование в окне сохраняет прежние ключи для всех обработчиков и ПК."""
    return [column["field"] if column["name"] else "" for column in read_columns(sheet)]


def check_name(columns, name, field, except_number=None):
    if not name.strip() or len(name.splitlines()) != 1:
        raise ValueError("Название должно быть непустым и занимать одну строку.")
    for column in columns:
        if column["number"] == except_number or not column["name"]:
            continue
        if column["name"] == name or column["field"] == field:
            raise ValueError("Название или назначение этой колонки уже используется.")


def header_request(sheet, number, name, field, previous_note=""):
    # Назначение хранится в Google, поэтому переименование работает на другом ПК.
    lines = [line for line in previous_note.splitlines() if not line.startswith(NOTE_PREFIX)]
    lines.append(NOTE_PREFIX + field)
    return {
        "updateCells": {
            "range": {
                "sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": number - 1, "endColumnIndex": number,
            },
            "rows": [{"values": [{
                "userEnteredValue": {"stringValue": name}, "note": "\n".join(lines),
            }]}],
            "fields": "userEnteredValue,note",
        }
    }


def rename_header(sheet, number, expected_name, name):
    """Имя и назначение меняются одним запросом; строки вакансий не затрагиваются."""
    columns = read_columns(sheet, refresh=True)
    if number < 1 or number > len(columns) or columns[number - 1]["name"] != expected_name:
        raise ValueError("Шапка изменилась. Загрузите колонки заново.")
    column = columns[number - 1]
    name = name.strip()
    field = column["field"] or name
    check_name(columns, name, field, except_number=number)
    sheet.spreadsheet.batch_update({
        "requests": [header_request(sheet, number, name, field, column["note"])]
    })
    return read_columns(sheet, refresh=True)


def add_header(sheet, name):
    """Вставляет новую колонку, сдвигая существующие данные, а не затирая их."""
    # Размер сетки мог измениться после предыдущего добавления в этом окне.
    sheet = sheet.spreadsheet.get_worksheet_by_id(sheet.id)
    columns = read_columns(sheet, refresh=True)
    name = name.strip()
    check_name(columns, name, name)
    position = max((column["number"] for column in columns if column["name"]), default=0)
    if position >= sheet.col_count:
        insert = {"appendDimension": {"sheetId": sheet.id, "dimension": "COLUMNS", "length": 1}}
    else:
        insert = {"insertDimension": {
            "range": {"sheetId": sheet.id, "dimension": "COLUMNS",
                      "startIndex": position, "endIndex": position + 1},
            "inheritFromBefore": position > 0,
        }}
    sheet.spreadsheet.batch_update({
        "requests": [insert, header_request(sheet, position + 1, name, name)]
    })
    return read_columns(sheet, refresh=True)


def delete_header(sheet, number, expected_name):
    """Очищает только заголовок. Назначение и все значения под ним сохраняются."""
    columns = read_columns(sheet, refresh=True)
    if number < 1 or number > len(columns) or columns[number - 1]["name"] != expected_name:
        raise ValueError("Шапка изменилась. Загрузите колонки заново.")
    column = columns[number - 1]
    sheet.spreadsheet.batch_update({
        "requests": [header_request(sheet, number, "", column["field"], column["note"])]
    })
    return read_columns(sheet, refresh=True)
