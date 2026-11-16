# run.py

from argparse import ArgumentParser
from datetime import date

from core.run_options import FILE_COMMANDS, RunOptions


# Этапы запускаются отдельно; каждый компьютер использует нужную команду.
COMMANDS = (
    "search", "fill", "collect-html", "check", "send", "import-html", "import-folder",
    "ai", "desktop-send", "requirements", "process-html", "draft-html", "import-results",
    "import-telegram",
)


def run_command(command, html_file=None, options=None, submit=False, data_dir=None, channel=None):
    """Подключает только модуль выбранного этапа."""
    options = options or RunOptions()
    options.validate(command)
    if submit and command != "desktop-send":
        raise ValueError("--submit применим только к desktop-send.")
    if data_dir is not None and command not in FILE_COMMANDS:
        raise ValueError("--data-dir применим только к этапам локальных снимков.")
    if channel is not None and command != "import-telegram":
        raise ValueError("--channel применим только к import-telegram.")
    if command == "import-telegram":
        if not html_file or not channel:
            raise ValueError("Укажите JSON-файл и --channel https://t.me/channel_name.")
        from workflows.import_telegram import main
        return main(html_file, channel, options, data_dir=data_dir)
    if command == "desktop-send":
        from desktop.process import main
        return main(options, submit=submit)
    # Импортируем только выбранный этап: команды hh не загружают ИИ-модуль.
    if command == "search":
        from workflows.search import process_vacancies
        return process_vacancies()
    if command == "fill":
        from workflows.fill import process_links
        return process_links(options)
    if command == "collect-html":
        from workflows.collect_html import main
        return main(options)
    if command == "check":
        from workflows.check_responses import check_responses
        return check_responses(options)
    if command == "send":
        from workflows.send_applications import send_applications
        return send_applications(options)
    if command in ("import-html", "import-folder"):
        from workflows.import_hh_links import main
        return main(html_file, folder=command == "import-folder")
    if command == "import-results":
        from workflows.import_results import main
        return main(options, data_dir=data_dir)
    if command in ("process-html", "draft-html"):
        from workflows.process_html import main
        return main(options, command, data_dir=data_dir)
    if command == "requirements":
        from workflows.keywords import main
        return main(options)
    if command == "ai":
        from ai.process_ai import main
        return main(options)
    raise ValueError(f"Неизвестная команда: {command}")


def main():
    parser = ArgumentParser(description="Запуск одного этапа обработки вакансий.")
    parser.add_argument("command", choices=COMMANDS)
    # Файловый вход используют импорт выдач hh и импорт сообщений Telegram.
    parser.add_argument("html_file", nargs="?", help="HTML, папка выдач hh или JSON-экспорт Telegram")
    parser.add_argument("--data-dir", help="Папка снимков для process-html, draft-html, import-results или import-telegram")
    parser.add_argument("--channel", help="Публичный канал для import-telegram: https://t.me/channel_name")
    parser.add_argument("--start-row", type=int, default=2, help="Начальная строка таблицы, от 2")
    parser.add_argument("--limit", type=int, help="Лимит; send — новых откликов, import-results — новых строк")
    parser.add_argument("--checked-from", type=date.fromisoformat, help="Дата проверки с YYYY-MM-DD")
    parser.add_argument("--checked-to", type=date.fromisoformat, help="Дата проверки по YYYY-MM-DD включительно")
    parser.add_argument("--include-unchecked", action="store_true", help="Включить пустую дату в диапазон check")
    parser.add_argument("--submit", action="store_true",
                        help="Только desktop-send: разрешить реальные отправки; без флага — проба открытого окна")
    args = parser.parse_args()
    if args.submit and args.command != "desktop-send":
        parser.error("--submit применим только к desktop-send.")

    if args.command in ("import-html", "import-folder", "import-telegram") and not args.html_file:
        parser.error("Укажите путь к файлу или папке импорта.")
    if args.command not in ("import-html", "import-folder", "import-telegram") and args.html_file:
        parser.error("Входной файл нужен только командам импорта.")
    if args.command == "import-telegram" and not args.channel:
        parser.error("Укажите --channel https://t.me/channel_name.")
    if args.channel is not None and args.command != "import-telegram":
        parser.error("--channel применим только к import-telegram.")
    if args.data_dir is not None and args.command not in FILE_COMMANDS:
        parser.error("--data-dir применим только к этапам локальных снимков.")
    options = RunOptions(
        args.start_row, args.limit, args.checked_from, args.checked_to, args.include_unchecked,
    )
    try:
        options.validate(args.command)
    except ValueError as error:
        parser.error(str(error))
    try:
        return run_command(args.command, args.html_file, options, submit=args.submit,
                           data_dir=args.data_dir, channel=args.channel)
    except KeyboardInterrupt:
        print("\nЗапуск остановлен пользователем.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
