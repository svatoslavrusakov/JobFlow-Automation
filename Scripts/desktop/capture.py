"""Выделение фрагмента неподвижного снимка; клики в браузер не передаются."""

import math
import tkinter as tk
from tkinter import messagebox, ttk


class CropDialog(tk.Toplevel):
    def __init__(self, parent, image, hint, on_save):
        from PIL import ImageTk
        super().__init__(parent)
        self.title("Выделите образец")
        self.image, self.on_save = image, on_save
        self.start = self.selection = self.rectangle = None
        # Уменьшаем только показ снимка: сохраняемый образец берём из оригинала.
        self.scale = min(1, (self.winfo_screenwidth() - 100) / image.width, (self.winfo_screenheight() - 180) / image.height)
        preview = image.resize((int(image.width * self.scale), int(image.height * self.scale)))
        self.photo = ImageTk.PhotoImage(preview)
        ttk.Label(self, text=hint, wraplength=800).pack(anchor="w", padx=8, pady=6)
        self.canvas = tk.Canvas(self, width=preview.width, height=preview.height, highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.bind("<ButtonPress-1>", self._begin)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._finish)
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Сохранить выделение", command=self._save).pack(side="left")
        ttk.Button(bar, text="Отмена", command=self.destroy).pack(side="right")
        self.transient(parent.winfo_toplevel())
        self.grab_set()

    def _point(self, event):
        """Ограничивает выделение границами показанного изображения."""
        return max(0, min(event.x, self.photo.width())), max(0, min(event.y, self.photo.height()))

    def _begin(self, event):
        self.start = self._point(event)
        self.selection = None
        if self.rectangle is not None:
            self.canvas.delete(self.rectangle)
        self.rectangle = self.canvas.create_rectangle(*self.start, *self.start, outline="red", width=2)

    def _drag(self, event):
        if self.start:
            self.canvas.coords(self.rectangle, *self.start, *self._point(event))

    def _finish(self, event):
        if not self.start:
            return
        end = self._point(event)
        x1, x2 = sorted((self.start[0], end[0]))
        y1, y2 = sorted((self.start[1], end[1]))
        # Деление возвращает координаты оригинала; округление наружу сохраняет края.
        self.selection = (
            math.floor(x1 / self.scale), math.floor(y1 / self.scale),
            min(self.image.width, math.ceil(x2 / self.scale)),
            min(self.image.height, math.ceil(y2 / self.scale)),
        )

    def _save(self):
        if self.selection is None or min(self.selection[2]-self.selection[0], self.selection[3]-self.selection[1]) < 12:
            messagebox.showerror("Выделение", "Выделите фрагмент размером хотя бы 12×12 пикселей.", parent=self)
            return
        try:
            self.on_save(self.image, self.selection)
        except (OSError, ValueError) as error:
            messagebox.showerror("Образец", str(error), parent=self)
            return
        self.destroy()
