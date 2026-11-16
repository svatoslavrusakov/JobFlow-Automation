"""Поля отбора строк для окна запуска."""

from datetime import date
import tkinter as tk
from tkinter import ttk

from core.run_options import RunOptions, TABLE_COMMANDS, FILE_COMMANDS


class OptionsPanel(ttk.LabelFrame):
    def __init__(self, parent, show_dates=True):
        super().__init__(parent, text="Параметры запуска", padding=8)
        self.start_row = tk.StringVar()
        self.limit = tk.StringVar()
        self.checked_from = tk.StringVar()
        self.checked_to = tk.StringVar()
        self.include_unchecked = tk.BooleanVar(value=False)
        self.controls = []

        common = ttk.Frame(self)
        common.pack(fill="x")
        dates = ttk.LabelFrame(
            self, text="Только «Проверить ответы»: дата последней проверки", padding=5,
        )
        if show_dates:
            dates.pack(fill="x", pady=(7, 0))

        for panel, labels in (
            (common, (("Со строки (необязательно):", self.start_row), ("Лимит:", self.limit))),
            (dates, (("С:", self.checked_from), ("По:", self.checked_to))),
        ):
            for column, (label, variable) in enumerate(labels):
                ttk.Label(panel, text=label).grid(row=0, column=column * 2, sticky="w", padx=4)
                entry = ttk.Entry(panel, textvariable=variable, width=15)
                entry.grid(row=0, column=column * 2 + 1, sticky="ew", padx=4, pady=3)
                self.controls.append(entry)
            panel.columnconfigure(1, weight=1)
            panel.columnconfigure(3, weight=1)

        checkbox = ttk.Checkbutton(
            dates, text="Включать ещё не проверенные",
            variable=self.include_unchecked,
        )
        checkbox.grid(row=1, column=0, columnspan=4, sticky="w", padx=4)
        self.controls.append(checkbox)
        ttk.Label(
            dates, text="Даты YYYY-MM-DD. Пустые поля — без фильтра дат.",
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=4)
        ttk.Label(
            self, text="Пустое поле «Со строки» — автоотбор. При заполнении: первая ссылка с пустым статусом. "
            "Пустой лимит — как раньше. Для поиска и импорта HTML отбор строк не применяется. "
            "Файловые этапы сайтов и Telegram используют только лимит.",
            wraplength=700,
        ).pack(anchor="w", pady=(6, 0))

    def read(self, command):
        """Читает только параметры, применимые к выбранной кнопке."""
        if command in FILE_COMMANDS:
            # Для файлов учитываем только лимит; строка и даты относятся к таблице.
            try:
                options = RunOptions(limit=int(self.limit.get()) if self.limit.get().strip() else None)
            except ValueError:
                raise ValueError("Лимит должен быть целым числом.") from None
            options.validate(command)
            return options
        if command not in TABLE_COMMANDS:
            return RunOptions()
        try:
            start_text = self.start_row.get().strip()
            # 2 — нижняя граница после заголовков; подходящую строку выберет очередь.
            start_row = int(start_text) if start_text else 2
            limit = int(self.limit.get()) if self.limit.get().strip() else None
        except ValueError:
            raise ValueError("Начальная строка и лимит должны быть целыми числами.") from None
        checked_from = checked_to = None
        if command == "check":
            try:
                checked_from = date.fromisoformat(self.checked_from.get().strip()) if self.checked_from.get().strip() else None
                checked_to = date.fromisoformat(self.checked_to.get().strip()) if self.checked_to.get().strip() else None
            except ValueError:
                raise ValueError("Укажите даты проверки в формате YYYY-MM-DD.") from None
        options = RunOptions(
            start_row, limit, checked_from, checked_to,
            self.include_unchecked.get() if command == "check" else False,
        )
        options.validate(command)
        return options

    def set_enabled(self, enabled):
        for control in self.controls:
            control.configure(state="normal" if enabled else "disabled")
