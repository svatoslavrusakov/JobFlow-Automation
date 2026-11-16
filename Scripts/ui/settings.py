"""Вкладка общих настроек; ключ вводится отдельно и никогда не попадает в JSON."""

from copy import deepcopy
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hh import browser
from tables import google_connection
from .delays import DelayPanel
from core.settings_defaults import PROJECT_DIR
from core import settings_store


class SettingsPanel(ttk.Frame):
    def __init__(self, parent, run_job, on_saved):
        super().__init__(parent, padding=8)
        self.run_job, self.on_saved = run_job, on_saved
        self.values = settings_store.load_settings()
        self.variables = {}
        self.controls = []
        self.browse_buttons = {}
        self.key_mode = tk.StringVar(value="file")
        self.new_key = tk.StringVar()
        self.message = tk.StringVar(value="Изменения действуют после сохранения, со следующего запуска этапа.")
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True)
        connection, paths = ttk.Frame(tabs, padding=10), ttk.Frame(tabs, padding=10)
        tabs.add(connection, text="Подключения")
        tabs.add(paths, text="Файлы и поиск")
        self._connections(connection)
        self._paths(paths)
        self.delays = DelayPanel(tabs, self.values)
        tabs.add(self.delays, text="Паузы и ожидания")
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        save = ttk.Button(footer, text="Сохранить настройки", command=self._save)
        save.pack(side="left")
        self.controls.append(save)
        ttk.Label(footer, textvariable=self.message, wraplength=690).pack(side="left", padx=12)
        self._key_controls()

    def _entry(self, frame, key, label, row, browse=None, choices=None):
        variable = tk.StringVar(value=str(self.values[key]))
        self.variables[key] = variable
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        entry = ttk.Combobox(frame, textvariable=variable, values=choices) if choices is not None else ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self.controls.append(entry)
        if browse:
            button = ttk.Button(frame, text="Выбрать…", command=lambda: self._browse(variable, browse))
            button.grid(row=row, column=2, padx=4)
            self.controls.append(button)
            self.browse_buttons[key] = button
        frame.columnconfigure(1, weight=1)
        return entry

    def _button(self, frame, label, command, row, column=2):
        button = ttk.Button(frame, text=label, command=command)
        button.grid(row=row, column=column, padx=4, pady=4, sticky="ew")
        self.controls.append(button)

    def _connections(self, frame):
        ttk.Label(frame, text="ИИ: Gemini; каталог моделей не подтверждает квоту генерации.").grid(row=0, column=0, columnspan=3, sticky="w")
        self.model_entry = self._entry(frame, "ai_model", "Модель:", 1, choices=[])
        self._button(frame, "Каталог моделей", self._models, 1)
        modes = ttk.Frame(frame)
        modes.grid(row=2, column=0, columnspan=3, sticky="w")
        for label, value in (("Ключ из файла", "file"), ("Ввести новый ключ", "manual")):
            button = ttk.Radiobutton(modes, text=label, value=value, variable=self.key_mode, command=self._key_controls)
            button.pack(side="left", padx=5)
            self.controls.append(button)
        self.key_file_entry = self._entry(frame, "ai_key_file", "Файл API-ключа:", 3, browse="file")
        ttk.Label(frame, text="Новый ключ:").grid(row=4, column=0, sticky="w", padx=4)
        self.key_entry = ttk.Entry(frame, textvariable=self.new_key, show="*")
        self.key_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)
        self.controls.append(self.key_entry)
        ttk.Label(frame, text="Введённый ключ сохраняется отдельно в data/ai_key.txt. Пустое поле сохраняет прежний ключ.", wraplength=760).grid(row=5, column=0, columnspan=3, sticky="w", pady=5)
        self.sheet_entry = self._entry(frame, "spreadsheet", "Google: имя, ID или ссылка:", 6)
        self.worksheet_entry = self._entry(frame, "worksheet", "Лист по умолчанию:", 7, choices=[])
        self._entry(frame, "credentials_file", "Файл доступа Google:", 8, browse="file")
        self._button(frame, "Проверить Google", self._google, 7)
        self._entry(frame, "chrome_address", "Адрес Chrome:", 9)
        self._button(frame, "Проверить Chrome", self._chrome, 9)
        self._entry(frame, "chrome_executable", "Программа Chrome:", 10, browse="file")
        self._entry(frame, "chrome_profile", "Папка профиля Chrome:", 11, browse="directory")
        self._button(frame, "Открыть Chrome", self._open_chrome, 12)
        ttk.Label(frame, text="VPN переключается вручную. Проверки используют сохранённые настройки.", wraplength=760).grid(row=12, column=0, columnspan=2, sticky="w", pady=6)

    def _paths(self, frame):
        paths = (
            ("resume_file", "Резюме для ИИ (TXT UTF-8):", "file"),
            ("prompt_file", "Шаблон промпта:", "file"),
            ("requirements_prompt_file", "Промпт ключевых слов:", "file"),
            ("html_prompt_file", "Промпт HTML сайтов:", "file"),
            ("search_url_file", "Файл ссылки поиска:", "file"),
            ("html_dir", "Папка HTML-снимков:", "directory"),
            ("telegram_dir", "Папка сообщений Telegram:", "directory"),
            ("sound_file", "Звуковой файл:", "file"),
            ("pages_to_scrape", "Страниц поиска:", None),
            ("ai_max_rows", "Лимит ИИ по умолчанию:", None),
            ("ai_pause_every", "Пауза ИИ после N вакансий:", None),
            ("ai_pause_seconds", "Длительность паузы ИИ, сек.:", None),
        )
        for row, (key, label, browse) in enumerate(paths):
            self._entry(frame, key, label, row, browse=browse)
        self.variables["blacklist"] = tk.StringVar(value="; ".join(self.values["blacklist"]))
        ttk.Label(frame, text="Чёрный список через ;").grid(row=len(paths), column=0, sticky="w")
        blacklist = ttk.Entry(frame, textvariable=self.variables["blacklist"])
        blacklist.grid(row=len(paths), column=1, columnspan=2, sticky="ew", pady=4)
        self.controls.append(blacklist)
        self.sound_enabled = tk.BooleanVar(value=self.values["sound_enabled"])
        sound = ttk.Checkbutton(frame, text="Звук при капче", variable=self.sound_enabled)
        sound.grid(row=len(paths) + 1, column=0, columnspan=2, sticky="w", pady=8)
        self.controls.append(sound)

    def _browse(self, variable, kind):
        path = filedialog.askdirectory(parent=self) if kind == "directory" else filedialog.askopenfilename(parent=self)
        if path:
            variable.set(path)

    def _key_controls(self):
        manual = self.key_mode.get() == "manual"
        self.key_entry.configure(state="normal" if manual else "disabled")
        self.key_file_entry.configure(state="disabled" if manual else "normal")
        self.browse_buttons["ai_key_file"].configure(state="disabled" if manual else "normal")

    def read_values(self, validate=True):
        values = deepcopy(self.values)
        for key, variable in self.variables.items():
            values[key] = variable.get().strip()
        for key in ("pages_to_scrape", "ai_max_rows", "ai_pause_every", "ai_pause_seconds"):
            try:
                values[key] = int(values[key])
            except ValueError:
                if not validate and values[key] == str(self.values[key]):
                    values[key] = self.values[key]
                else:
                    raise ValueError(f"«{key}»: нужно целое число.") from None
        values["blacklist"] = [word.strip() for word in values["blacklist"].split(";") if word.strip()]
        values["sound_enabled"] = self.sound_enabled.get()
        values.update(self.delays.read_values())
        if self.key_mode.get() == "manual":
            values["ai_key_file"] = "data/ai_key.txt"
        if validate:
            settings_store.validate_settings(values)
        return values

    def _save(self):
        try:
            values = self.read_values()
            key = self.new_key.get().strip() if self.key_mode.get() == "manual" else ""
            if key:
                if "\n" in key or "\r" in key:
                    raise ValueError("API-ключ должен занимать одну строку.")
                settings_store.write_private_file(PROJECT_DIR / "data" / "ai_key.txt", key + "\n")
            settings_store.save_settings(values)
        except (ValueError, OSError) as error:
            messagebox.showerror("Настройки", str(error), parent=self)
            return
        self.values = values
        self.variables["ai_key_file"].set(values["ai_key_file"])
        self.new_key.set("")
        self.key_mode.set("file")
        self._key_controls()
        self.message.set("Настройки сохранены. Следующий этап использует новые значения.")
        self.on_saved(values)

    def require_saved(self):
        # Запуск проверяет только свои настройки; общая валидация остаётся при сохранении.
        values = self.read_values(validate=False)
        if values != settings_store.load_settings() or self.new_key.get().strip():
            raise ValueError("Сначала сохраните настройки.")
        return values

    def _google(self):
        try:
            values = self.require_saved()
        except ValueError as error:
            messagebox.showerror("Подключение", str(error), parent=self)
            return
        def work():
            spreadsheet = google_connection.open_spreadsheet(values)
            return [sheet.title for sheet in spreadsheet.worksheets()]
        self.run_job("Проверяю Google Таблицу…", work, self._google_ready)

    def _google_ready(self, titles):
        self.worksheet_entry.configure(values=titles)
        self.message.set(f"Google подключён. Найдено листов: {len(titles)}.")

    def _chrome(self):
        try:
            values = self.require_saved()
        except ValueError as error:
            messagebox.showerror("Подключение", str(error), parent=self)
            return
        self.run_job("Проверяю порт Chrome…",
            lambda: browser.read_chrome_version(values["chrome_address"], values["timeouts"]["CHROME_DEBUG_TIMEOUT"]),
            lambda version: self.message.set(f"Chrome {version} доступен. Навигация не выполнялась."))

    def _models(self):
        from ai import models, settings
        try:
            self.require_saved()
            options = settings.load_settings()
        except ValueError as error:
            messagebox.showerror("Модели", str(error), parent=self)
            return
        def ready(names):
            self.model_entry.configure(values=names)
            self.message.set(f"Моделей в каталоге: {len(names)}. Квота генерации не проверялась.")
        self.run_job("Читаю каталог Gemini…", lambda: models.list_models(options), ready)

    def _open_chrome(self):
        try:
            values = self.require_saved()
            browser.launch_browser(values)
        except (ValueError, OSError) as error:
            messagebox.showerror("Chrome", str(error), parent=self)

    def set_enabled(self, enabled):
        for control in self.controls:
            control.configure(state="normal" if enabled else "disabled")
        self.delays.set_enabled(enabled)
        if enabled:
            self._key_controls()
