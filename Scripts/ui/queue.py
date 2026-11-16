"""Список очереди; письмо выбранной строки открывается в отдельном редакторе."""

import tkinter as tk
from tkinter import messagebox, ttk

from tables.queue_preview import PAGE_SIZE, PREVIEW_STAGES, load_preview, read_preview_page
from .letter import LetterWindow
from tables.letter_review import read_review


class QueueWindow(tk.Toplevel):
    def __init__(self, parent, snapshot, run_job):
        super().__init__(parent)
        self.title("Предпросмотр очереди")
        self.geometry("1150x650")
        self.minsize(850, 450)
        self.snapshot, self.run_job = snapshot, run_job
        self.page = 0
        self.busy = False
        self.shown = {}
        self.letter_window = None
        self.show_all = tk.BooleanVar(value=False)
        self.summary = tk.StringVar()
        self.page_text = tk.StringVar()
        self.detail = tk.StringVar(value="Выберите строку, чтобы увидеть ссылку и пояснение.")
        self._build_controls()
        self._build_table()
        self._build_footer()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.transient(parent)
        self.grab_set()
        self._load_page()

    def _build_controls(self):
        """Сводка очереди и переключатель отображения пропусков."""
        ttk.Label(self, textvariable=self.summary, wraplength=1080).pack(anchor="w", padx=12, pady=10)
        bar = ttk.Frame(self, padding=(12, 0))
        bar.pack(fill="x")
        self.toggle = ttk.Checkbutton(bar, text="Показать также пропуски", variable=self.show_all, command=self._change_view)
        self.toggle.pack(side="left")
        self.refresh = ttk.Button(bar, text="Обновить очередь", command=self._refresh)
        self.refresh.pack(side="right")

    def _build_table(self):
        """Список с прежними колонками и полосами прокрутки."""
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        columns = [
            ("number", "Строка", 60), ("id", "ID", 90), ("company", "Компания", 160),
            ("title", "Вакансия", 240), ("status", "Статус", 75), ("letter", "Письмо", 90),
            ("decision", "Результат отбора", 110), ("reason", "Пояснение", 340),
        ]
        if self.snapshot["command"] == "check":
            columns.insert(5, ("checked", "Дата проверки", 145))
        self.fields = [name for name, _, _ in columns]
        self.tree = ttk.Treeview(frame, columns=self.fields, show="headings", selectmode="browse")
        for name, label, width in columns:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=50)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.tree.bind("<Double-1>", lambda event: self._open_letter())
        self.tree.tag_configure("Ошибка", foreground="#A02020")
        self.tree.tag_configure("Пропуск", foreground="#666666")
        self.tree.tag_configure("Изменена", foreground="#9A5900")

    def _build_footer(self):
        """Пояснение выбранной строки, страницы и закрытие окна."""
        ttk.Label(self, textvariable=self.detail, wraplength=1080).pack(anchor="w", padx=12)
        footer = ttk.Frame(self, padding=12)
        footer.pack(fill="x")
        self.open_letter = ttk.Button(footer, text="Открыть письмо", command=self._open_letter, state="disabled")
        self.open_letter.pack(side="left", padx=(0, 12))
        self.previous = ttk.Button(footer, text="Назад", command=lambda: self._turn(-1))
        self.previous.pack(side="left")
        self.next = ttk.Button(footer, text="Далее", command=lambda: self._turn(1))
        self.next.pack(side="left", padx=8)
        ttk.Label(footer, textvariable=self.page_text).pack(side="left", padx=8)
        ttk.Button(footer, text="Закрыть", command=self._close).pack(side="right")
        note = "Состояние hh, авторизация и полные исходные данные проверяются при запуске этапа. Просмотр ничего не отправляет."
        if self.snapshot["command"] == "send":
            note += " Лимит ограничивает новые подтверждённые отклики; кандидатов может быть больше."
        ttk.Label(self, text=note, wraplength=1080).pack(anchor="w", padx=12, pady=(0, 12))

    def _entries(self):
        return [entry for entry in self.snapshot["entries"] if self.show_all.get() or entry["selected"]]

    def _busy(self, busy):
        self.busy = busy
        self.open_letter.configure(state="normal" if not busy and self.tree.selection() else "disabled")
        self.toggle.configure(state="disabled" if busy else "normal")
        self.refresh.configure(state="disabled" if busy else "normal")
        total = len(self._entries())
        self.previous.configure(state="normal" if not busy and self.page > 0 else "disabled")
        self.next.configure(state="normal" if not busy and (self.page + 1) * PAGE_SIZE < total else "disabled")

    def _clear_page(self, message):
        """Старые строки не должны выглядеть как результат новой загрузки."""
        self.tree.delete(*self.tree.get_children())
        self.shown.clear()
        self.detail.set(message)

    def _load_page(self):
        entries = self._entries()
        self.page = min(self.page, max(0, (len(entries) - 1) // PAGE_SIZE))
        selected = sum(entry["selected"] for entry in self.snapshot["entries"])
        limit = self.snapshot["limit"]
        self.summary.set(
            f"{self.snapshot['title']} · {dict(PREVIEW_STAGES)[self.snapshot['command']]} · "
            f"со строки {self.snapshot['options'].start_row} · лимит {limit if limit is not None else 'не задан'}\n"
            f"По параметрам выбрано: {selected}. Снимок: {self.snapshot['created_at']}"
        )
        self._clear_page("Загружаю выбранную страницу…")
        self._busy(True)
        self.page_text.set("Читаю видимые строки…")
        page = entries[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
        self.run_job("Читаю поля выбранной страницы…",
                     lambda: read_preview_page(self.snapshot, page), self._show_page, on_error=self._error)

    def _show_page(self, rows):
        if not self.winfo_exists():
            return
        self.shown = {str(row["number"]): row for row in rows}
        for key, row in self.shown.items():
            self.tree.insert("", "end", iid=key, values=[row[name] for name in self.fields], tags=(row["decision"],))
        pages = max(1, (len(self._entries()) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_text.set(f"Страница {self.page + 1} из {pages}")
        self.detail.set("Выберите строку, чтобы увидеть ссылку и пояснение.")
        self._busy(False)

    def _select(self, event=None):
        selected = self.tree.selection()
        row = self.shown.get(selected[0]) if selected else None
        self.open_letter.configure(state="normal" if row and not self.busy else "disabled")
        if row:
            self.detail.set(f"Строка {row['number']}: {row['link']}\n{row['reason']}")

    def _open_letter(self):
        selected = self.tree.selection()
        row = self.shown.get(selected[0]) if selected else None
        if self.busy or row is None:
            return
        queued = {"ID": row["id"], "Ссылка": row["link"]}
        number = row["number"]
        self._busy(True)
        self.run_job("Читаю письмо выбранной вакансии…",
            lambda: read_review(self.snapshot["sheet"], number, queued),
            lambda current: self._show_letter(number, current), on_error=self._error)

    def _show_letter(self, number, row):
        if self.winfo_exists():
            self._busy(False)
            self.letter_window = LetterWindow(
                self, self.snapshot["sheet"], number, row, self.run_job, self._refresh,
            )

    def _turn(self, step):
        self.page += step
        self._load_page()

    def _change_view(self):
        self.page = 0
        self._load_page()

    def _refresh(self):
        self._clear_page("Обновляю очередь…")
        self._busy(True)
        self.run_job("Обновляю снимок очереди…",
            lambda: load_preview(self.snapshot["title"], self.snapshot["command"], self.snapshot["options"]),
            self._replace_snapshot, on_error=self._error)

    def _replace_snapshot(self, snapshot):
        if self.winfo_exists():
            self.snapshot, self.page = snapshot, 0
            self._load_page()

    def _error(self, message):
        if self.winfo_exists():
            self._clear_page("Обновите очередь или выберите другую страницу.")
            self.page_text.set("Не удалось загрузить страницу.")
            self._busy(False)
            messagebox.showerror("Предпросмотр очереди", message, parent=self)

    def _close(self):
        # Закрытие очереди не обходит проверку несохранённого письма.
        child = self.letter_window
        if child is not None and child.winfo_exists():
            child._close()
            if child.winfo_exists():
                return
        self.destroy()
