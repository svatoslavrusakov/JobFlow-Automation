"""Заполняет ключевые слова в исходных строках, не меняя статусы откликов."""

from urllib.parse import urlsplit

from gspread.exceptions import APIError
from gspread.utils import rowcol_to_a1
from requests.exceptions import RequestException

from ai import pacing, requirements, settings
from tables.google_connection import request_with_retry
from core.row_queue import select_stage_rows
from core.run_options import RunOptions
from tables import sheets
from core import stop_control
from core import utils

KEYWORDS = "Ключевые слова"
FIELDS = ("ID", "Ссылка", "Описание", KEYWORDS)
CHUNK_SIZE = 50


def process_row(sheet, headers, number, before, ai_options, template):
    """Проверяет исходник, получает слова и записывает только одну ячейку."""
    if any(before[field].lstrip().startswith("=") for field in FIELDS):
        raise ValueError("В исходных данных находится формула.")
    # Внешние URL не очищаем; для hh проверяем соответствие ID и ссылки.
    if utils.is_hh_host(urlsplit(before["Ссылка"]).hostname or ""):
        vacancy_id, _ = utils.parse_vacancy_link(before["Ссылка"])
        if before["ID"].strip() not in ("", vacancy_id):
            raise ValueError("ID вакансии не совпадает со ссылкой.")
    result = requirements.analyze(before["Описание"], ai_options, template)
    if request_with_retry(sheets.read_headers, sheet, required_headers=FIELDS) != headers:
        raise ValueError("Шапка изменилась во время анализа.")
    current = request_with_retry(sheets.read_row_fields, sheet, [number], headers, FIELDS)[number]
    if current != before:
        raise ValueError("Строка изменилась во время анализа; запись отменена.")
    address = rowcol_to_a1(number, headers.index(KEYWORDS) + 1)
    request_with_retry(sheet.batch_update, [{"range": address, "values": [[result]]}], value_input_option="RAW")


def analyze_rows(sheet, headers, options, ai_options, template):
    """Пропускает готовые ячейки; лимит и пауза считаются по попыткам анализа."""
    rows = request_with_retry(sheets.read_vacancy_rows, sheet, fields=("ID", "Ссылка", KEYWORDS), headers=headers)
    queue = select_stage_rows(rows, "requirements", options, apply_limit=False)
    queue = [(number, row) for number, row in queue if not row[KEYWORDS].strip()]
    limit = options.limit if options.limit is not None else ai_options["max_rows"]
    processed, saved, errors = 0, 0, 0
    # Полные описания читаем небольшими порциями, а не целым столбцом.
    for offset in range(0, len(queue), CHUNK_SIZE):
        stop_control.check()
        chunk = queue[offset:offset + CHUNK_SIZE]
        if request_with_retry(sheets.read_headers, sheet, required_headers=FIELDS) != headers:
            raise ValueError("Шапка исходного листа изменилась.")
        fields = request_with_retry(sheets.read_row_fields, sheet, [n for n, _ in chunk], headers, FIELDS)
        for number, queued in chunk:
            stop_control.check()
            before = fields[number]
            if before[KEYWORDS].strip() or not before["Описание"].strip():
                continue
            try:
                if any(before[field].strip() != queued[field].strip() for field in ("ID", "Ссылка")):
                    raise ValueError("ID или ссылка изменились после чтения очереди.")
                pacing.pause_before(processed, ai_options)
                processed += 1
                process_row(sheet, headers, number, before, ai_options, template)
            except ValueError as error:
                print(f"Строка {number}: ключевые слова не записаны: {error}")
                errors += 1
            else:
                saved += 1
                print(f"Строка {number}: ключевые слова сохранены.")
            if processed >= limit:
                return saved, errors
    return saved, errors


def main(options=None):
    """Запускает один этап с общими настройками модели, пауз и отбора строк."""
    options = options or RunOptions()
    options.validate("requirements")
    try:
        ai_options = settings.load_settings(required_paths=("ai_key_file", "requirements_prompt_file"))
        settings.read_text(ai_options["key_file"])
        template = settings.load_prompt(ai_options["requirements_prompt_file"], markers=("{{description}}",))
        sheet = sheets.init_google_sheet()
        if sheet is None:
            return 1
        headers = request_with_retry(sheets.read_headers, sheet, required_headers=FIELDS)
        saved, errors = analyze_rows(sheet, headers, options, ai_options, template)
        print(f"Ключевые слова: сохранено {saved}; ошибок {errors}.")
        return 1 if errors else 0
    except KeyboardInterrupt:
        print("Анализ остановлен. Записанные ключевые слова сохранены.")
        return 130
    except (ValueError, RuntimeError, APIError, RequestException, OSError) as error:
        print(f"Анализ ключевых слов остановлен: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
