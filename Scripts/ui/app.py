"""Небольшое окно для запуска готовых этапов обработки вакансий."""

import importlib
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from core import config
from core.settings_store import load_settings, resolve_path
from .runner import StageRunner
from .scroll import ScrollFrame
from .workflow import WorkflowPanel
from core.run_options import LOCAL_COMMANDS
from .settings import SettingsPanel
from .columns import ColumnsPanel
from .jobs import BackgroundJobs
from .desktop import DesktopPanel
from .queue import QueueWindow
from tables.queue_preview import PREVIEW_STAGES, load_preview


HH_STAGES = (
    ("import-html", "Ссылки из HTML"),
    ("import-folder", "HTML из папки"),
    ("fill", "Заполнить по ссылкам"),
    ("search", "Поиск hh"),
    ("ai", "Подготовить письма"),
    ("requirements", "Ключевые слова"),
    ("send", "Отправить отклики"),
    ("check", "Проверить ответы"),
)

COMPANY_STAGES = (
    ("collect-html", "Сохранить HTML сайтов"),
    ("process-html", "Распознать HTML сайтов"),
    ("draft-html", "Подготовить письма сайтов"),
    ("import-results", "Импортировать результаты"),
)


TELEGRAM_STAGES = (
    ("import-telegram", "Сообщения из JSON"),
    ("process-html", "Распознать сообщения"),
    ("draft-html", "Подготовить письма"),
    ("import-results", "Импортировать результаты"),
)


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto_hh — этапы обработки")
        # На небольшом экране оставляем место для заголовка окна и панели задач.
        width = min(1000, self.winfo_screenwidth() - 80)
        height = min(820, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(min(850, width), min(450, height))
        self.runner = StageRunner()
        self.sheet_name = tk.StringVar(value=config.WORKSHEET_NAME)
        self.state_text = tk.StringVar(value="Готово к запуску")
        self.table_text = tk.StringVar(value=f"Таблица: {config.SPREADSHEET_NAME}")
        self._build_window()
        self.after(100, self._poll_output)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_window(self):
        """Показывает выбранную вкладку, этапы и журнал одного запуска."""
        tabs = self.tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True)
        # Работа с источниками отделена от общих настроек и редактора колонок.
        self.hh_tabs = ttk.Notebook(tabs)
        tabs.add(self.hh_tabs, text="hh")
        self.hh_panel = WorkflowPanel(self.hh_tabs, self, HH_STAGES,
            "hh: импорт выдачи → заполнение → ИИ → проверка писем → отправка → ответы.", preview=True)
        self.hh_tabs.add(self.hh_panel, text="Этапы")
        self.company_panel = WorkflowPanel(tabs, self, COMPANY_STAGES,
            "Сайты компаний: сохранить HTML → включить VPN вручную → распознать → подготовить письмо. "
            "Затем выключить VPN и импортировать в отдельный лист. Локальные этапы и импорт используют "
            "только лимит. Отправка внешних откликов пока вручную.")
        tabs.add(self.company_panel, text="Сайты компаний")
        self.telegram_panel = WorkflowPanel(tabs, self, TELEGRAM_STAGES,
            "Telegram: экспорт одного публичного канала в JSON → импорт сообщений → ИИ → письмо → "
            "импорт в отдельный лист. Укажите адрес канала, соответствующий экспорту. "
            "Папка сообщений задаётся в настройках. Отправка откликов вручную.", directory_key="telegram_dir")
        tabs.add(self.telegram_panel, text="Telegram")
        self.work_panels = (self.hh_panel, self.company_panel, self.telegram_panel)
        self.active_panel = self.hh_panel

        settings = ScrollFrame(tabs)
        self.settings_panel = SettingsPanel(settings.content, self.run_job, self._settings_saved)
        self.settings_panel.pack(fill="both", expand=True)
        tabs.add(settings, text="Настройки")
        self.columns_panel = ColumnsPanel(tabs, self.sheet_name, self.run_job)
        tabs.add(self.columns_panel, text="Колонки таблицы")
        desktop = ScrollFrame(self.hh_tabs)
        self.desktop_panel = DesktopPanel(
            desktop.content, self.run_job, lambda submit: self._start("desktop-send", submit=submit),
            self.settings_panel.require_saved,
        )
        self.desktop_panel.pack(fill="both", expand=True)
        self.hh_tabs.add(desktop, text="Экранный режим")
        self.jobs = BackgroundJobs(self, self._set_busy, self.state_text)

    def _append_log(self, text):
        self.active_panel.append_log(text)

    def _preview_queue(self, panel):
        worksheet = self.sheet_name.get().strip()
        try:
            if not worksheet:
                raise ValueError("Укажите лист Google Таблицы.")
            self.settings_panel.require_saved()
            command = next(name for name, label in PREVIEW_STAGES if label == panel.queue_mode.get())
            options = panel.options_panel.read(command)
        except ValueError as error:
            messagebox.showerror("Предпросмотр очереди", str(error), parent=self)
            return
        self.run_job("Читаю очередь из таблицы…",
            lambda: load_preview(worksheet, command, options),
            lambda snapshot: QueueWindow(self, snapshot, self.run_job))

    def _prepare_start(self, command, panel, submit):
        """Проверяет настройки и возвращает лист, отбор строк и дополнительные аргументы."""
        worksheet = self.sheet_name.get().strip()
        if not worksheet and command not in LOCAL_COMMANDS:
            raise ValueError("Укажите название вкладки Google Таблицы.")
        self.settings_panel.require_saved()
        options = panel.options_panel.read(command)
        extra_args = ["--submit"] if submit else []
        # У Telegram своя папка; обработчики остаются общими с сайтами.
        if panel.directory_key:
            directory = resolve_path(load_settings()[panel.directory_key])
            extra_args += ["--data-dir", str(directory)]
        if command == "desktop-send":
            from desktop import profile
            from desktop.process import require_dependencies
            require_dependencies()
            profile.validate(profile.load_profile(), submit=submit)
        return worksheet, options, extra_args

    def _choose_import(self, command):
        """Выбирает вход импорта; None означает отмену, (None, []) — этап без файла."""
        if command == "import-folder":
            path = filedialog.askdirectory(title="Выберите папку сохранённых выдач hh", parent=self)
        elif command == "import-html":
            path = filedialog.askopenfilename(title="Выберите сохранённую выдачу hh", parent=self,
                filetypes=[("HTML", "*.html *.htm"), ("Все файлы", "*.*")])
        elif command == "import-telegram":
            path = filedialog.askopenfilename(title="JSON-экспорт одного канала Telegram", parent=self,
                filetypes=[("JSON", "*.json")])
        else:
            return None, []
        if not path:
            return None
        if command == "import-telegram":
            channel = simpledialog.askstring("Канал Telegram",
                "Адрес канала из экспорта: https://t.me/channel_name", parent=self)
            return (path, ["--channel", channel.strip()]) if channel and channel.strip() else None
        return path, []

    def _start(self, command, panel=None, submit=False):
        """Готовит запуск, запрашивает подтверждение отправки и передаёт этап runner."""
        panel = panel or self.hh_panel
        if self.runner.process is not None or self.jobs.busy:
            messagebox.showinfo("Этап работает", "Дождитесь завершения текущего действия.", parent=self)
            return
        try:
            worksheet, options, extra_args = self._prepare_start(command, panel, submit)
        except ValueError as error:
            messagebox.showerror("Параметры запуска", str(error), parent=self)
            return
        selected = self._choose_import(command)
        if selected is None:
            return
        input_file, import_args = selected
        extra_args += import_args
        if (command == "send" or command == "desktop-send" and submit) and not messagebox.askyesno(
            "Отправка откликов",
            f"Вкладка: {worksheet}\nСо строки: "
            f"{options.start_row if panel.options_panel.start_row.get().strip() else 'первой подходящей'}\n"
            f"Новых откликов: {options.limit if options.limit is not None else 'без лимита'}\n\n"
            "Отправить готовые отклики работодателям?", parent=self,
        ):
            return
        try:
            self.runner.start(command, worksheet, input_file, options, extra_args=extra_args)
        except (OSError, RuntimeError, ValueError) as error:
            messagebox.showerror("Запуск", str(error), parent=self)
            return
        self.active_panel = panel
        if command == "desktop-send":
            self.tabs.select(self.hh_tabs)
            self.hh_tabs.select(self.hh_panel)
        target = "локальные файлы" if command in LOCAL_COMMANDS else f"вкладка «{worksheet}»"
        self._append_log(f"\nЗапуск: {command}; {target}\n")
        if command == "import-results":
            self._append_log("Добавляются новые записи; существующие ID и ссылки пропускаются.\n")
        if options.cli_args():
            self._append_log("Параметры: " + " ".join(options.cli_args()) + "\n")
        self.state_text.set(f"Работает: {command}")
        self._set_busy(True)

    def _set_busy(self, busy):
        """Не даёт менять подключение или шапку во время работы обработчика."""
        for panel in self.work_panels:
            panel.set_enabled(not busy, running=busy and self.runner.process is not None)
        self.settings_panel.set_enabled(not busy)
        self.columns_panel.set_enabled(not busy)
        self.desktop_panel.set_enabled(not busy)

    def run_job(self, title, work, on_done, on_error=None):
        """Общий фон для подключений, редактора заголовков и предпросмотра."""
        if self.runner.process is not None:
            messagebox.showinfo("Этап работает", "Дождитесь завершения этапа.", parent=self)
            return
        self.jobs.run(title, work, on_done, on_error=on_error)

    def _settings_saved(self, values):
        # Существующие модули используют тот же объект config, без перезапуска окна.
        importlib.reload(config)
        self.table_text.set(f"Таблица: {config.SPREADSHEET_NAME}")
        self.sheet_name.set(values["worksheet"])
        self.columns_panel.clear_loaded()

    def _stop(self):
        try:
            requested = self.runner.stop()
        except OSError as error:
            messagebox.showerror("Остановка", str(error))
            return
        if requested:
            self.state_text.set("Останавливается после текущего действия…")
            for panel in self.work_panels:
                panel.stop_button.configure(state="disabled")

    def _poll_output(self):
        try:
            while True:
                kind, value = self.runner.events.get_nowait()
                if kind == "line":
                    self._append_log(value)
                else:
                    self._append_log(f"Завершено, код {value}.\n")
                    self.runner.finish()
                    self.state_text.set("Готово к запуску")
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_output)

    def _close(self):
        if self.runner.process is not None or self.jobs.busy:
            messagebox.showinfo("Действие выполняется", "Дождитесь завершения действия. Для работающего этапа можно нажать «Остановить».", parent=self)
            return
        # Сначала закрываем дочернее окно: у него могут быть несохранённые правки.
        child = self.grab_current()
        if child is not None and child is not self:
            child.lift()
            return
        self.destroy()
