"""Панель черновика резюме: генерация, открытие JSON и локальный экспорт DOCX."""

from tkinter import filedialog, messagebox, ttk

from ai import resume
from ai import resume_docx


class ResumePanel(ttk.Frame):
    def __init__(self, parent, run_job, on_busy, notice):
        super().__init__(parent, padding=(12, 0, 12, 12))
        self.run_job, self.on_busy, self.notice = run_job, on_busy, notice
        self.row, self.path = {}, None
        self.enabled = True
        self.create_button = ttk.Button(self, text="Резюме → JSON", command=self.create_draft)
        self.create_button.pack(side="left")
        self.open_button = ttk.Button(self, text="Открыть JSON", command=self.open_draft)
        self.open_button.pack(side="left", padx=(8, 0))
        self.docx_button = ttk.Button(self, text="Сохранить DOCX", command=self.export_docx)
        self.docx_button.pack(side="left", padx=8)
        self.set_enabled(True)

    def set_vacancy(self, row):
        """Смена исходных данных снимает выбор файла; статус и письмо могут меняться."""
        if any(row.get(field, "") != self.row.get(field, "") for field in resume.SOURCE_FIELDS):
            self.path = None
        self.row = dict(row)
        self.set_enabled(self.enabled)

    def set_enabled(self, enabled):
        """Родитель блокирует панель вместе с письмом на время фоновой работы."""
        self.enabled = enabled
        for button in (self.create_button, self.open_button):
            button.configure(state="normal" if enabled else "disabled")
        self.docx_button.configure(state="normal" if enabled and self.path is not None else "disabled")

    def open_draft(self):
        """Читает сохранённый JSON без обращения к модели."""
        if not self.enabled:
            return
        path = filedialog.askopenfilename(
            parent=self, title="Открыть черновик резюме",
            initialdir=str(resume.OUTPUT_DIR), filetypes=[("Черновик резюме", "*.json")],
        )
        if not path:
            return
        vacancy = dict(self.row)
        # Отмена сохраняет прежний путь; выбранный файл сначала проверяется.
        self.path = None
        self.on_busy(True)
        self.notice.set("Проверяю выбранный черновик…")
        self.run_job("Открываю черновик резюме…",
            lambda: resume_docx.read_draft(path, vacancy=vacancy),
            lambda _: self._ready(path), on_error=self._error)

    def create_draft(self):
        """Передаёт в фон снимок вакансии; виджеты из фонового потока не читаются."""
        if not self.enabled:
            return
        vacancy = dict(self.row)
        try:
            resume.check_vacancy(vacancy)
        except ValueError as error:
            messagebox.showerror("Черновик резюме", str(error), parent=self)
            return
        self.path = None
        self.on_busy(True)
        self.notice.set("Подготавливаю черновик резюме; потребуется ручная проверка…")
        self.run_job("Подготавливаю резюме…", lambda: resume.create_resume_draft(vacancy),
                     self._ready, on_error=self._error)

    def _ready(self, path):
        if self.winfo_exists():
            self.path = path
            self.on_busy(False)
            self.notice.set(f"Черновик резюме: {path}. Откройте JSON и проверьте разделы, цитаты и вопросы.")

    def export_docx(self):
        """Экспорт повторно проверяет JSON и вакансию, не вызывая ИИ."""
        if not self.enabled or self.path is None:
            return
        path, vacancy = self.path, dict(self.row)
        self.on_busy(True)
        self.notice.set("Создаю DOCX-черновик…")
        self.run_job("Сохраняю DOCX…", lambda: resume_docx.create_docx(path, vacancy=vacancy),
                     self._exported, on_error=self._error)

    def _exported(self, path):
        if self.winfo_exists():
            self.on_busy(False)
            self.notice.set(f"DOCX-черновик: {path}. Откройте файл и проверьте оформление и содержание.")

    def _error(self, message):
        if self.winfo_exists():
            # Локальная ошибка не делает состояние Google неопределённым и не стирает письмо.
            self.on_busy(False)
            self.notice.set("Работа с черновиком не завершена. Введённое письмо сохранено в окне.")
            messagebox.showerror("Черновик резюме", message, parent=self)
