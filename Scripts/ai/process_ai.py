# process_ai.py

from core import stop_control

from tables import sheets
from core.row_queue import select_stage_rows
from core.run_options import RunOptions

from ai import draft, pacing
from ai import settings
from ai import sheet as ai_sheet
from ai.result import InvalidAIResult


def process_row(sheet, row_number, queued, resume, options, template, processed=0):
    """Проверяет одну строку, готовит письмо и сохраняет результат."""
    # После чтения очереди строку могли изменить на другом компьютере.
    try:
        current = ai_sheet.read_row(sheet, row_number, queued)
    except ValueError as error:
        print(f"Строка {row_number}: пропущена: {error}")
        return "skipped"

    # Пауза только перед настоящей попыткой, после проверки строки.
    pacing.pause_before(processed, options)
    try:
        answer = draft.create_draft(current, resume, options, template)
    except InvalidAIResult as error:
        # Ошибка формата оставляет new для следующей попытки.
        print(f"Строка {row_number}: ответ ИИ отклонён: {error}")
        return "error"

    # После генерации ещё раз сверяем строку перед записью результата.
    try:
        status = ai_sheet.save_result(sheet, row_number, current, answer)
    except ValueError as error:
        print(f"Строка {row_number}: запись отменена: {error}")
        return "changed"  # Запрос ИИ уже выполнен, даже если строку не записали.

    print(f"Строка {row_number}: письмо сохранено, статус {status}.")
    return "saved"


def main(run_options=None):
    """Обрабатывает ограниченное число новых вакансий выбранного листа."""
    run_options = run_options or RunOptions()
    run_options.validate("ai")
    try:
        options = settings.load_settings()
        resume = settings.read_text(options["resume_file"])
        template = settings.load_prompt(options["prompt_file"])
    except ValueError as error:
        print(f"Настройки ИИ: {error}")
        return 1

    # Для этого этапа нужен доступ к таблице; браузер hh не используется.
    sheet = sheets.init_google_sheet()
    if sheet is None:
        return 1
    try:
        # Нужные колонки проверяем до вызова платного API.
        rows = sheets.read_vacancy_rows(
            sheet,
            fields=("ID", "Ссылка", "Статус"),
            required_headers=ai_sheet.AI_HEADERS,
        )
    except ValueError as error:
        print(f"Ошибка заголовков таблицы: {error}")
        return 1
    except Exception as error:
        print(f"Ошибка чтения таблицы ({type(error).__name__}).")
        return 1

    # Те же правила отбора использует предпросмотр, без вызова API.
    queue = select_stage_rows(rows, "ai", run_options, ai_limit=options["max_rows"])
    if not queue:
        print("Нет вакансий со статусом new.")
        return 0

    counts = {"saved": 0, "skipped": 0, "error": 0}
    processed = 0
    for row_number, queued in queue:
        stop_control.check()
        try:
            outcome = process_row(
                sheet, row_number, queued, resume, options, template, processed,
            )
        except RuntimeError as error:
            print(f"Строка {row_number}: {error}")
            return 1
        except Exception as error:
            # Не печатаем ответ API или промпт с резюме.
            print(f"Строка {row_number}: ошибка API или таблицы "
                  f"({type(error).__name__}).")
            return 1
        counts["skipped" if outcome == "changed" else outcome] += 1
        # Только пропуск до запроса не учитываем при расчёте паузы.
        if outcome != "skipped":
            processed += 1

    print(
        f"Итог ИИ: сохранено {counts['saved']}, "
        f"пропущено {counts['skipped']}, ошибок {counts['error']}."
    )
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
