"""Проверенные vacancy.json и draft.json → новые строки выбранного листа Google."""

from gspread.exceptions import APIError
from requests.exceptions import RequestException

from ai import html_draft
from ai.sheet import AI_HEADERS, build_result_values
from core import stop_control, utils
from core.run_options import RunOptions
from core.settings_store import load_settings, resolve_path
from html_tools import html_storage
from tables import google_connection, sheets
from tables.import_rows import import_rows


def read_results(directory):
    """Читает готовые пары без модели и ключа; ошибки файлов не скрываются."""
    if not directory.is_dir():
        raise ValueError("Папка HTML-снимков не найдена.")
    vacancies, errors = [], 0
    for folder in sorted(directory.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        stop_control.check()
        try:
            source, _ = html_storage.read_snapshot(folder)
            vacancy = html_storage.read_vacancy(folder, source)
            if vacancy is None:
                continue
            document = html_draft.read_draft(folder, vacancy)
            if document is None:
                continue  # Неподготовленная вакансия не получает done.
            values = {**vacancy, **build_result_values(document["result"])}
            # Итоговые письмо и списки тоже должны помещаться в ячейку Google.
            if any(len(str(value)) > 45000 for value in values.values()):
                raise ValueError("Результат слишком длинный для ячейки таблицы.")
            vacancies.append(values)
        except (OSError, ValueError) as error:
            print(f"Снимок {folder.name}: импорт пропущен: {error}")
            errors += 1
    return vacancies, errors


def main(options=None, data_dir=None):
    """Импортирует только новые ID/URL; готовые строки не перезаписывает."""
    options = options or RunOptions()
    options.validate("import-results")
    try:
        utils.validate_delays(required=("DELAY_IMPORT_BATCH",))
        directory = resolve_path(data_dir or load_settings()["html_dir"])
        vacancies, errors = read_results(directory)
        if not vacancies:
            print("Нет готовых пар vacancy.json и draft.json для импорта.")
            return 1 if errors else 0
        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1
        headers = google_connection.request_with_retry(sheets.read_headers, sheet, required_headers=AI_HEADERS)
        added = import_rows(sheet, vacancies, headers=headers, limit=options.limit)
        print(f"Импортировано: {added}; готовых файлов: {len(vacancies)}; ошибок файлов: {errors}.")
        return 1 if errors else 0
    except KeyboardInterrupt:
        print("Импорт остановлен. Сохранённые строки остаются в таблице.")
        return 130
    except (OSError, ValueError, APIError, RequestException) as error:
        print(f"Импорт результатов остановлен: {error}")
        # Google мог принять партию до потери ответа: автоматически её не повторяем.
        print("Если ошибка возникла при записи, проверьте последнюю партию в таблице.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
