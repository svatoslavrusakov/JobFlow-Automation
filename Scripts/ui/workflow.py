"""Общая панель запуска: вкладки различаются кнопками, а не копиями обработчиков."""

import tkinter as tk
from tkinter import ttk

from tables.queue_preview import PREVIEW_STAGES
from .options import OptionsPanel
from .scroll import ScrollFrame


class WorkflowPanel(ScrollFrame):
    def __init__(self, parent, app, stages, description, preview=False, directory_key=None):
        super().__init__(parent, padding=14)
        frame = self.content
        self.directory_key = directory_key  # У источников разные папки, обработчики этапов общие.
        self.buttons = []
        ttk.Label(frame, text=description, wraplength=850).pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, textvariable=app.table_text).pack(anchor="w")
        sheet = ttk.Frame(frame)
        sheet.pack(fill="x", pady=(8, 12))
        ttk.Label(sheet, text="Лист Google Таблицы:").pack(side="left")
        # Подключение общее; параметры отбора и журнал у каждого направления свои.
        self.sheet_entry = ttk.Entry(sheet, textvariable=app.sheet_name)
        self.sheet_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.options_panel = OptionsPanel(frame, show_dates=preview)
        self.options_panel.pack(fill="x", pady=(0, 10))
        self.queue_combo = None
        if preview:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=(0, 10))
            ttk.Label(row, text="Очередь для:").pack(side="left")
            self.queue_mode = tk.StringVar(value=dict(PREVIEW_STAGES)["send"])
            self.queue_combo = ttk.Combobox(row, textvariable=self.queue_mode,
                values=[label for _, label in PREVIEW_STAGES], state="readonly", width=35)
            self.queue_combo.pack(side="left", padx=8)
            button = ttk.Button(row, text="Показать очередь", command=lambda: app._preview_queue(self))
            button.pack(side="left")
            self.buttons.append(button)
        group = ttk.LabelFrame(frame, text="Запустить один этап", padding=8)
        group.pack(fill="x")
        for index, (command, label) in enumerate(stages):
            button = ttk.Button(group, text=label, command=lambda value=command: app._start(value, self))
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
            self.buttons.append(button)
        group.columnconfigure((0, 1), weight=1)
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(10, 8))
        ttk.Label(controls, textvariable=app.state_text).pack(side="left")
        self.stop_button = ttk.Button(controls, text="Остановить после текущего действия",
                                      command=app._stop, state="disabled")
        self.stop_button.pack(side="right")
        log = ttk.LabelFrame(frame, text="Журнал этого направления", padding=6)
        log.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log)
        scrollbar.pack(side="right", fill="y")
        self.log = tk.Text(log, height=12, wrap="word", state="disabled", yscrollcommand=scrollbar.set)
        self.log.pack(fill="both", expand=True)
        scrollbar.configure(command=self.log.yview)

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_enabled(self, enabled, running=False):
        """Один обработчик блокировки для всех направлений; запуск остаётся один."""
        state = "normal" if enabled else "disabled"
        self.sheet_entry.configure(state=state)
        self.options_panel.set_enabled(enabled)
        if self.queue_combo is not None:
            self.queue_combo.configure(state="readonly" if enabled else "disabled")
        for button in self.buttons:
            button.configure(state=state)
        self.stop_button.configure(state="normal" if running else "disabled")
