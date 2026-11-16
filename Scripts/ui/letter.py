"""Редактор одного письма; сетевые действия выполняются через общий фон окна."""

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from tables import letter_review
from .resume import ResumePanel


class LetterWindow(tk.Toplevel):
    def __init__(self, parent, sheet, number, row, run_job, on_changed):
        super().__init__(parent)
        self.title("Проверка сопроводительного письма")
        self.geometry("1100x720")
        self.minsize(850, 550)
        self.sheet, self.number = sheet, number
        self.run_job, self.on_changed = run_job, on_changed
        self.busy = self.needs_reload = self.refresh_parent = False
        self.identity = tk.StringVar()
        self.notice = tk.StringVar()
        self.context = {}
        self._build_window()
        self._show_row(row)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.transient(parent)
        self.grab_set()

    def _build_window(self):
        ttk.Label(self, textvariable=self.identity, wraplength=1040).pack(anchor="w", padx=12, pady=10)
        body = ttk.Frame(self, padding=(12, 0))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="Сопроводительное письмо").grid(row=0, column=0, sticky="w")
        self.editor = ScrolledText(body, wrap="word", undo=True, width=55)
        self.editor.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        tabs = ttk.Notebook(body)
        tabs.grid(row=1, column=1, sticky="nsew")
        for field, title in (
            ("Описание", "Вакансия"), ("Требования к отклику", "Требования"), ("Подводные камни", "Риски"),
        ):
            text = ScrolledText(tabs, wrap="word", width=38, state="disabled")
            tabs.add(text, text=title)
            self.context[field] = text
        self._build_buttons()

    def _build_buttons(self):
        ttk.Label(self, textvariable=self.notice, wraplength=1040).pack(anchor="w", padx=12, pady=10)
        bar = ttk.Frame(self, padding=(12, 0, 12, 12))
        bar.pack(fill="x")
        self.draft_button = ttk.Button(bar, text="Сохранить без одобрения", command=lambda: self._save(False))
        self.draft_button.pack(side="left")
        self.approve_button = ttk.Button(bar, text="Одобрить → done", command=lambda: self._save(True))
        self.approve_button.pack(side="left", padx=8)
        self.reload_button = ttk.Button(bar, text="Перечитать строку", command=self._reload)
        self.reload_button.pack(side="left")
        self.close_button = ttk.Button(bar, text="Закрыть", command=self._close)
        self.close_button.pack(side="right")
        self.documents = ResumePanel(self, self.run_job, self._set_busy, self.notice)
        self.documents.pack(fill="x")

    def _show_row(self, row):
        """Снимок хранится для сверки; текст письма не выводится в журнал."""
        self.documents.set_vacancy(row)
        self.row = dict(row)
        self.original_text = letter_review.normalize_letter(row["Сопроводительное"])
        self.block_reason = ""
        try:
            letter_review.require_editable(row)
        except ValueError as error:
            self.block_reason = str(error)
        self.identity.set(
            f"Строка {self.number} · ID {row['ID']} · {row.get('Компания', '')}\n"
            f"{row.get('Заголовок', '')}\n{row['Ссылка']}\n"
            f"Статус: {row['Статус']} · Зарплата: {row.get('Зарплата', '')} · Оценка ИИ: {row.get('Оценка ИИ', '')}"
        )
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.original_text)
        self.editor.edit_reset()
        for field, widget in self.context.items():
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", row.get(field, "") or "Нет данных.")
            widget.configure(state="disabled")
        self.needs_reload = False
        self._set_busy(False)
        self.notice.set(self.block_reason or "Сохранение без одобрения → thinking. Одобрение → done.")

    def _set_busy(self, busy):
        self.busy = busy
        editable = not busy and not self.needs_reload and not self.block_reason
        self.editor.configure(state="normal" if editable else "disabled")
        for button in (self.draft_button, self.approve_button):
            button.configure(state="normal" if editable else "disabled")
        self.documents.set_enabled(not busy and not self.needs_reload)
        for button in (self.reload_button, self.close_button):
            button.configure(state="disabled" if busy else "normal")

    def _text(self):
        # Убираем только служебный последний перевод строки Tkinter, сохраняя абзацы.
        return self.editor.get("1.0", "end-1c")

    def _discard_allowed(self):
        return self._text() == self.original_text or messagebox.askyesno(
            "Несохранённое письмо", "Отменить несохранённые изменения письма?", parent=self,
        )

    def _save(self, approve):
        if self.busy or self.needs_reload or self.block_reason:
            return
        # Виджеты читаются в потоке Tkinter; фон получает готовые строки и снимок.
        text, before = self._text(), dict(self.row)
        try:
            letter_review.build_review_values(before, before, text, approve)
        except ValueError as error:
            messagebox.showerror("Письмо не сохранено", str(error), parent=self)
            return
        self.refresh_parent = True
        self._set_busy(True)
        self.notice.set("Сохраняю письмо и статус…")
        self.run_job("Сохраняю проверенное письмо…",
            lambda: letter_review.save_review(self.sheet, self.number, before, text, approve),
            self._saved, on_error=self._error)

    def _saved(self, row):
        if self.winfo_exists():
            self._show_row(row)
            self.notice.set(f"Письмо сохранено. Статус: {row['Статус']}. Отклик не отправлялся.")

    def _reload(self):
        if self.busy or not self._discard_allowed():
            return
        queued = dict(self.row)
        self._set_busy(True)
        self.notice.set("Перечитываю строку…")
        self.run_job("Перечитываю письмо…",
            lambda: letter_review.read_review(self.sheet, self.number, queued),
            self._loaded, on_error=self._error)

    def _loaded(self, row):
        if self.winfo_exists():
            self._show_row(row)

    def _error(self, message):
        if self.winfo_exists():
            # После неопределённого результата сначала читаем Google, а не повторяем запись.
            self.needs_reload = True
            self._set_busy(False)
            self.notice.set("Действие не подтверждено. Текст оставлен в окне; перечитайте строку.")
            messagebox.showerror("Проверка письма", message, parent=self)

    def _close(self):
        if self.busy:
            self.notice.set("Дождитесь завершения текущего действия.")
            return
        if not self._discard_allowed():
            return
        parent = self.master
        self.destroy()
        if parent.winfo_exists():
            # После закрытия дочернего окна возвращаем управление окну очереди.
            parent.grab_set()
            if self.refresh_parent:
                self.on_changed()
