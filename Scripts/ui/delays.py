"""Редактор пауз и тайм-аутов; значения применяются при сохранении настроек."""

from copy import deepcopy
import math
import tkinter as tk
from tkinter import messagebox, ttk

from core.settings_defaults import DELAY_DEFAULTS, TIMEOUT_LABELS, default_settings


class DelayPanel(ttk.Frame):
    def __init__(self, parent, values):
        super().__init__(parent, padding=8)
        self.minimum = tk.StringVar()
        self.maximum = tk.StringVar()
        self.controls = []
        self.tree = ttk.Treeview(self, columns=("label", "min", "max"), show="headings", height=14)
        for key, label, width in (("label", "Пауза или ожидание, секунды", 480), ("min", "Минимум / значение", 140), ("max", "Максимум", 100)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        editor = ttk.Frame(self)
        editor.grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        for column, (label, variable) in enumerate((("Минимум / значение:", self.minimum), ("Максимум:", self.maximum))):
            ttk.Label(editor, text=label).grid(row=0, column=column * 2, padx=4)
            entry = ttk.Entry(editor, textvariable=variable, width=12)
            entry.grid(row=0, column=column * 2 + 1)
            self.controls.append(entry)
        self.apply_button = ttk.Button(editor, text="Применить к строке", command=self._apply_click)
        self.apply_button.grid(row=0, column=4, padx=8)
        self.reset_button = ttk.Button(self, text="Стандартные интервалы", command=lambda: self.set_values(default_settings()))
        self.reset_button.grid(row=2, column=0, sticky="w")
        self.controls += [self.apply_button, self.reset_button]
        ttk.Label(self, text="Пауза выполняется всегда; тайм-аут ограничивает ожидание результата. Изменения сохраняются общей кнопкой.", wraplength=760).grid(row=3, column=0, sticky="w", pady=8)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.set_values(values)

    def set_values(self, values):
        self.values = {group: deepcopy(values[group]) for group in ("delays", "timeouts")}
        self.tree.delete(*self.tree.get_children())
        for name, pair in self.values["delays"].items():
            shown = pair if isinstance(pair, (list, tuple)) and len(pair) == 2 else ("Ошибка", "")
            self.tree.insert("", "end", iid="delays/" + name, values=(DELAY_DEFAULTS[name][2], *shown))
        for name, value in self.values["timeouts"].items():
            self.tree.insert("", "end", iid="timeouts/" + name, values=(TIMEOUT_LABELS[name], value, ""))
        self.tree.selection_set(self.tree.get_children()[0])
        self._select()

    def _select(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        group, name = selected[0].split("/", 1)
        value = self.values[group][name]
        if group == "delays":
            pair = value if isinstance(value, (list, tuple)) and len(value) == 2 else ("", "")
            self.minimum.set(str(pair[0]))
            self.maximum.set(str(pair[1]))
        else:
            self.minimum.set(str(value))
            self.maximum.set("")
        self.shown_values = (self.minimum.get(), self.maximum.get())

    def apply_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        group, name = selected[0].split("/", 1)
        try:
            minimum = float(self.minimum.get())
            maximum = float(self.maximum.get()) if group == "delays" else None
        except ValueError:
            raise ValueError("Интервалы вводятся числами; дробная часть — через точку.") from None
        if not math.isfinite(minimum) or (group == "delays" and (
            not math.isfinite(maximum) or not 0 <= minimum <= maximum
        )) or (group == "timeouts" and minimum <= 0):
            raise ValueError("Для паузы: 0 ≤ минимум ≤ максимум. Для ожидания: положительное число.")
        if name == "CHROMEDRIVER_NETWORK_TIMEOUT" and not minimum.is_integer():
            raise ValueError("Подбор драйвера: укажите целое число секунд.")
        self.values[group][name] = [minimum, maximum] if group == "delays" else minimum
        label = DELAY_DEFAULTS[name][2] if group == "delays" else TIMEOUT_LABELS[name]
        self.tree.item(selected[0], values=(label, minimum, maximum if maximum is not None else ""))
        self.shown_values = (self.minimum.get(), self.maximum.get())

    def _apply_click(self):
        try:
            self.apply_selected()
        except ValueError as error:
            messagebox.showerror("Интервал", str(error), parent=self)

    def read_values(self):
        # Неизменённая ошибочная настройка другого этапа остаётся для его проверки.
        if (self.minimum.get(), self.maximum.get()) != self.shown_values:
            self.apply_selected()
        return deepcopy(self.values)

    def set_enabled(self, enabled):
        for control in self.controls:
            control.configure(state="normal" if enabled else "disabled")
