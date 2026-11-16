"""Параметры одного запуска, общие для консоли и интерфейса."""

from dataclasses import dataclass
from datetime import date


# review используется только окном писем, а не отдельной командой run.py.
TABLE_COMMANDS = ("fill", "collect-html", "check", "send", "ai", "desktop-send", "review", "requirements")
# Файловый вход имеет лимит, но не начальную строку таблицы.
LOCAL_COMMANDS = ("process-html", "draft-html", "import-telegram")  # Эти этапы не подключаются к Google.
FILE_COMMANDS = LOCAL_COMMANDS + ("import-results",)


@dataclass(frozen=True)
class RunOptions:
    start_row: int = 2
    limit: int | None = None
    checked_from: date | None = None
    checked_to: date | None = None
    include_unchecked: bool = False

    def validate(self, command):
        """Проверяет параметры до чтения таблицы и открытия браузера."""
        if type(self.start_row) is not int or self.start_row < 2:
            raise ValueError("Начальная строка должна быть целым числом от 2.")
        if self.limit is not None and (type(self.limit) is not int or self.limit < 1):
            raise ValueError("Лимит должен быть положительным целым числом.")
        if self.checked_from and self.checked_to and self.checked_from > self.checked_to:
            raise ValueError("Начало диапазона дат позже его окончания.")
        if command in FILE_COMMANDS and self.start_row != 2:
            raise ValueError("Начальная строка неприменима к файловым этапам.")
        if command not in TABLE_COMMANDS + FILE_COMMANDS and self != RunOptions():
            raise ValueError("Отбор строк недоступен для выбранного этапа.")
        if command != "check" and (
            self.checked_from or self.checked_to or self.include_unchecked
        ):
            raise ValueError("Даты последней проверки применяются только к check.")

    def cli_args(self):
        """Передаёт параметры дочернему run.py без изменения файлов настроек."""
        args = []
        if self.start_row != 2:
            args += ["--start-row", str(self.start_row)]
        if self.limit is not None:
            args += ["--limit", str(self.limit)]
        for flag, value in (
            ("--checked-from", self.checked_from), ("--checked-to", self.checked_to),
        ):
            if value is not None:
                args += [flag, value.isoformat()]
        if self.include_unchecked:
            args.append("--include-unchecked")
        return args
