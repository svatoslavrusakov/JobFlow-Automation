"""Настройка образцов и запуск отдельного экранного режима."""

import tkinter as tk
from tkinter import messagebox, ttk
from uuid import uuid4

from desktop import profile


class DesktopPanel(ttk.Frame):
    def __init__(self, parent, run_job, launch, require_saved):
        super().__init__(parent, padding=12)
        self.run_job, self.launch, self.require_saved = run_job, launch, require_saved
        try:
            self.values = profile.load_profile()
        except ValueError:
            # Повреждённая калибровка не блокирует остальные вкладки.
            self.values = profile.default_profile()
            ttk.Label(self, text="Калибровка не читается. Сохраните новые образцы.", foreground="red").pack(anchor="w")
        self.controls = []
        self.capture_status = tk.StringVar(value="Выберите элемент и добавьте образец.")
        ttk.Label(
            self, text="Обычный Chrome без Selenium. Порт отладки не нужен. Сначала настройте образцы и проверьте заполнение открытого окна.",
            wraplength=900,
        ).pack(anchor="w")
        ttk.Label(
            self, text="Chrome — на основном мониторе. Сохраните размер окна, масштаб Windows и масштаб страницы. Escape или курсор в левый верхний угол — остановка.",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 10))
        self.tree = ttk.Treeview(self, columns=("name", "count"), show="headings", height=15, selectmode="browse")
        self.tree.heading("name", text="Элемент")
        self.tree.heading("count", text="Сохранено")
        self.tree.column("name", width=450)
        self.tree.column("count", width=100)
        self.tree.pack(fill="both", expand=True)
        self._refresh()
        self.tree.selection_set("dialog_area")
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=6)
        for title, action in (("Добавить образец", self._capture), ("Убрать образцы элемента", self._clear)):
            self._button(buttons, title, action).pack(side="left", padx=(0, 8))
        ttk.Label(self, textvariable=self.capture_status, wraplength=900).pack(anchor="w")
        fields = ttk.Frame(self)
        fields.pack(fill="x", pady=6)
        self.fields = {}
        for column, (key, title) in enumerate((
            ("confidence", "Точность 0.85–1"), ("typing_interval", "Секунд на символ"),
            ("countdown", "Старт через, с"),
        )):
            ttk.Label(fields, text=title).grid(row=0, column=column, sticky="w", padx=4)
            value = tk.StringVar(value=str(self.values[key]))
            self.fields[key] = value
            entry = ttk.Entry(fields, textvariable=value, width=20)
            entry.grid(row=1, column=column, padx=4, sticky="ew")
            self.controls.append(entry)
        self._button(fields, "Сохранить параметры", self._save).grid(row=1, column=3, padx=8)
        launch_bar = ttk.Frame(self)
        launch_bar.pack(fill="x", pady=8)
        self._button(launch_bar, "Проба: заполнить открытое окно", lambda: self._launch(False)).pack(side="left", padx=(0, 8))
        self._button(launch_bar, "Отправлять по экрану…", lambda: self._launch(True)).pack(side="left")
        ttk.Label(
            self, text="Лист, начальная строка, лимит и журнал — на вкладке «Работа». Проба обрабатывает одну строку done и не меняет таблицу. Образцы и настройки: data/desktop/ (вне Git).",
            wraplength=900,
        ).pack(anchor="w")
        ttk.Label(
            self, text="Необходимые библиотеки: python -m pip install -r requirements-desktop.txt",
        ).pack(anchor="w", pady=(8, 0))

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.controls.append(button)
        return button

    def _refresh(self):
        for key, (title, _) in profile.MARKERS.items():
            count = "есть" if key == "dialog_area" and self.values[key] else len(self.values["templates"].get(key, []))
            if self.tree.exists(key):
                self.tree.item(key, values=(title, count))
            else:
                self.tree.insert("", "end", iid=key, values=(title, count))

    def _selected(self):
        selected = self.tree.selection()
        if not selected:
            raise ValueError("Выберите элемент в списке.")
        return selected[0]

    def _read(self):
        values = dict(self.values)
        for key, variable in self.fields.items():
            try:
                values[key] = float(variable.get())
            except ValueError:
                raise ValueError("Параметры экрана должны быть числами.") from None
        profile.validate(values, ready=False)
        return values

    def _save(self):
        try:
            values = self._read()
            profile.save_profile(values)
            self.values = values
        except (ValueError, OSError) as error:
            messagebox.showerror("Параметры экрана", str(error), parent=self)
            return False
        return True

    def _capture(self):
        try:
            self.require_saved()
            key = self._selected()
            values = self._read()
            from desktop.process import require_dependencies
            require_dependencies()
        except (ValueError, OSError) as error:
            messagebox.showerror("Снимок", str(error), parent=self)
            return

        def work():
            from core import stop_control
            from desktop.window import ChromeWindow
            # Пользователь сам выбирает Chrome; программа окна не переключает.
            stop_control.pause(values["countdown"])
            window = ChromeWindow()
            image = window.capture()
            screen_size = [window.user.GetSystemMetrics(0), window.user.GetSystemMetrics(1)]
            return image, screen_size

        def done(result):
            self.capture_status.set("Снимок получен. Выделите нужный элемент.")
            from desktop.capture import CropDialog
            image, screen_size = result
            CropDialog(self, image, profile.MARKERS[key][1], lambda image, box: self._store(key, values, screen_size, image, box))

        self.capture_status.set(f"Переключитесь в Chrome: снимок через {values['countdown']:g} с.")
        self.run_job(f"Переключитесь в Chrome: снимок через {values['countdown']:g} с", work, done)

    def _store(self, key, values, screen_size, image, box):
        if key != "dialog_area" and (values["screen_size"] != screen_size or values["window_size"] != list(image.size)):
            raise ValueError("Сначала сохраните область окна отклика в этом размере Chrome.")
        values = {**values, "templates": dict(values["templates"])}
        if key == "dialog_area":
            if values["window_size"] and (values["window_size"] != list(image.size) or values["screen_size"] != screen_size):
                raise ValueError("Размер изменился. Уберите прежнюю область окна и создайте калибровку заново.")
            x1, y1, x2, y2 = box
            values.update(screen_size=screen_size, window_size=list(image.size), dialog_area=[x1, y1, x2-x1, y2-y1])
        else:
            sample = image.crop(box)
            profile.check_template(sample)
            profile.DIRECTORY.mkdir(parents=True, exist_ok=True)
            name = f"{key}_{uuid4().hex[:12]}.png"
            sample.save(profile.template_path(name))
            values["templates"][key] = [*values["templates"].get(key, []), name]
        profile.save_profile(values)
        self.values = values
        self._refresh()

    def _clear(self):
        try:
            key = self._selected()
            question = "Сбросить всю калибровку? Образцы остальных элементов тоже нужно будет снять заново." if key == "dialog_area" else "Убрать сохранённые образцы выбранного элемента?"
            if not messagebox.askyesno("Образцы", question, parent=self):
                return
            if key == "dialog_area":
                self.values.update(screen_size=[], window_size=[], dialog_area=[], templates={})
            else:
                self.values["templates"].pop(key, None)
            profile.save_profile(self.values)
            self._refresh()
        except (ValueError, OSError) as error:
            messagebox.showerror("Образцы", str(error), parent=self)

    def _launch(self, submit):
        if self._save():
            self.launch(submit)

    def set_enabled(self, enabled):
        for control in self.controls:
            control.configure(state="normal" if enabled else "disabled")
