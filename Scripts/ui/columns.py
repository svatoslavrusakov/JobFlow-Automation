"""Вкладка шапки Google Таблицы: названия, назначение и редактирование."""

import tkinter as tk
from tkinter import messagebox, ttk

from tables.column_catalog import COLUMNS
from tables import google_connection
from core import settings_store
from tables import table_columns


class ColumnsPanel(ttk.Frame):
    def __init__(self, parent, sheet_name, run_job):
        super().__init__(parent, padding=10)
        self.sheet_name, self.run_job = sheet_name, run_job
        self.sheet = None
        self.columns = {}
        self.loaded_target = None
        self.name = tk.StringVar()
        self.info = tk.StringVar(value="Загрузите заголовки выбранного листа. Вакансии целиком не читаются.")
        self.controls = []
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Лист:").pack(side="left")
        entry = ttk.Entry(top, textvariable=sheet_name)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        load = ttk.Button(top, text="Загрузить заголовки", command=self._load)
        load.pack(side="left")
        self.controls += [entry, load]
        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, pady=10)
        self.tree = ttk.Treeview(table, columns=("address","name","owner","required"), show="headings", selectmode="browse")
        for key, title, width in (("address","Ячейка",70),("name","Заголовок на листе",330),("owner","Кто заполняет",170),("required","Нужен для",140)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        ttk.Label(self, textvariable=self.info, wraplength=850, justify="left").pack(fill="x", pady=6)
        editor = ttk.Frame(self)
        editor.pack(fill="x", pady=6)
        ttk.Label(editor, text="Название:").pack(side="left")
        entry = ttk.Combobox(editor, textvariable=self.name, values=list(COLUMNS))
        entry.pack(side="left", fill="x", expand=True, padx=6)
        self.controls.append(entry)
        for label, command in (("Добавить",self._add),("Переименовать",self._rename),("Удалить заголовок",self._delete)):
            button = ttk.Button(editor, text=label, command=command)
            button.pack(side="left", padx=3)
            self.controls.append(button)
        ttk.Label(self, text="Удаляется только название в первой строке; данные под ним сохраняются. Переименование сохраняет назначение колонки.", wraplength=850).pack(anchor="w", pady=6)

    def clear_loaded(self):
        """Сбрасывает список после смены подключения, не изменяя сам лист."""
        self.sheet = None
        self.loaded_target = None
        self.columns = {}
        self.tree.delete(*self.tree.get_children())
        self.info.set("Настройки подключения изменены. Загрузите заголовки заново.")

    def _target(self):
        # Одного названия листа мало: оно может повторяться в другом документе.
        values = settings_store.load_settings()
        return values, (values["credentials_file"], values["spreadsheet"], self.sheet_name.get().strip())

    def _load(self):
        try:
            values, target = self._target()
        except ValueError as error:
            messagebox.showerror("Настройки", str(error), parent=self)
            return
        if not target[2]:
            messagebox.showerror("Лист", "Укажите название листа.", parent=self)
            return
        def work():
            sheet = google_connection.open_worksheet(values, target[2])
            return sheet, table_columns.read_columns(sheet, refresh=True)
        def ready(result):
            self.sheet, columns = result
            # Запоминаем подключение, для которого действительно получены эти заголовки.
            self.loaded_target = target
            self._show(columns)
        self.run_job("Читаю заголовки Google Таблицы…", work, ready)

    def _show(self, columns):
        self.columns = {str(column["number"]): column for column in columns}
        self.tree.delete(*self.tree.get_children())
        for key, column in self.columns.items():
            self.tree.insert("", "end", iid=key, values=(
                column["address"], column["name"] or "(без заголовка)",
                column["owner"], column["required"],
            ))
        self.info.set(f"Загружено позиций: {len(columns)}. Выберите колонку для пояснения.")

    def _select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        column = self.columns[selection[0]]
        self.name.set(column["name"] or column["field"])
        self.info.set(f"Назначение: {column['field'] or 'не задано'}. {column['explanation']}")

    def _ensure_loaded(self):
        """Не даёт править старый список после выбора другой таблицы или вкладки."""
        _, target = self._target()
        if self.sheet is None or target != self.loaded_target:
            raise ValueError("Загрузите заголовки для текущей таблицы и листа.")

    def _selected(self):
        self._ensure_loaded()
        selection = self.tree.selection()
        if not selection:
            raise ValueError("Выберите колонку в списке.")
        return self.columns[selection[0]]

    def _add(self):
        try:
            self._ensure_loaded()
            name = self.name.get().strip()
            table_columns.check_name(list(self.columns.values()), name, name)
        except ValueError as error:
            messagebox.showerror("Колонка", str(error), parent=self)
            return
        self.run_job("Добавляю заголовок…", lambda: table_columns.add_header(self.sheet, name), self._show)

    def _rename(self):
        try:
            column = self._selected()
            name = self.name.get().strip()
            table_columns.check_name(list(self.columns.values()), name, column["field"] or name, column["number"])
        except ValueError as error:
            messagebox.showerror("Колонка", str(error), parent=self)
            return
        if not messagebox.askyesno("Переименование",
            f"Ячейка {column['address']}: «{column['name']}» → «{name}».\nНазначение «{column['field'] or name}» и данные сохранятся.", parent=self):
            return
        self.run_job("Переименовываю заголовок…",
            lambda: table_columns.rename_header(self.sheet, column["number"], column["name"], name), self._show)

    def _delete(self):
        try:
            column = self._selected()
            if not column["name"]:
                raise ValueError("Этот заголовок уже пуст.")
        except ValueError as error:
            messagebox.showerror("Колонка", str(error), parent=self)
            return
        if not messagebox.askyesno("Удаление заголовка",
            f"Очистить {column['address']} — «{column['name']}»?\nДанные вакансий сохранятся.\nЭтапы, которым нужна колонка, не запустятся до восстановления заголовка.", parent=self):
            return
        # Сервис очищает только имя в первой строке; значения вакансий остаются.
        self.run_job("Удаляю заголовок…",
            lambda: table_columns.delete_header(self.sheet, column["number"], column["name"]), self._show)

    def set_enabled(self, enabled):
        for control in self.controls:
            control.configure(state="normal" if enabled else "disabled")
