"""Прокрутка длинных вкладок без изменения их кнопок и обработчиков."""

import tkinter as tk
from tkinter import ttk


class ScrollFrame(ttk.Frame):
    """Размещает обычную content-панель внутри прокручиваемой области."""
    def __init__(self, parent, padding=0):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, yscrollincrement=20)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = ttk.Frame(self.canvas, padding=padding)
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._resize)
        self.canvas.bind("<Configure>", self._resize)
        # События дочерних кнопок и полей доходят до окна; чужие вкладки отсекаем ниже.
        self.winfo_toplevel().bind("<MouseWheel>", self._wheel, add="+")

    def _resize(self, event=None):
        """Панель занимает доступную ширину, а лишняя высота уходит в прокрутку."""
        self.canvas.itemconfigure(
            self.window, width=self.canvas.winfo_width(),
            height=max(self.canvas.winfo_height(), self.content.winfo_reqheight()),
        )
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        """Прокручивает вкладку; журнал, списки и выбор модели сохраняют своё колесо."""
        if not isinstance(event.widget, tk.Widget) or not event.delta:
            return
        if not str(event.widget).startswith(str(self) + "."):
            return
        if event.widget.winfo_class() in ("Text", "Listbox", "Treeview", "TCombobox", "Scrollbar", "TScrollbar"):
            return
        if self.canvas.yview() == (0.0, 1.0):
            return
        direction = -1 if event.delta > 0 else 1
        # У колеса Windows шаг обычно 120; у трекпада он может быть меньше.
        steps = max(1, abs(event.delta) // 120)
        self.canvas.yview_scroll(direction * steps * 3, "units")
        return "break"
