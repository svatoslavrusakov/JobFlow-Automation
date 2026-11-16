"""Выполняет сетевую работу в фоне; виджеты обновляются только в потоке Tkinter."""

import queue
import threading
from tkinter import messagebox


class BackgroundJobs:
    def __init__(self, window, set_busy, state_text):
        self.window = window
        self.set_busy = set_busy
        self.state_text = state_text
        self.events = queue.Queue()
        self.busy = False
        window.after(100, self._poll)

    def run(self, title, work, on_done, on_error=None):
        if self.busy:
            raise RuntimeError("Дождитесь завершения текущего действия.")
        self.busy = True
        self.set_busy(True)
        self.state_text.set(title)
        threading.Thread(target=self._work, args=(work, on_done, on_error), daemon=True).start()

    def _work(self, work, on_done, on_error):
        try:
            self.events.put((True, work(), on_done, on_error))
        except Exception as error:
            # Содержимое файлов ключей и запросов сюда не передаётся.
            self.events.put((False, str(error), None, on_error))

    def _poll(self):
        try:
            success, result, on_done, on_error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.set_busy(False)
            self.state_text.set("Готово к запуску")
            callback = on_done if success else on_error
            if callback:
                try:
                    callback(result)
                except Exception as error:
                    messagebox.showerror("Результат действия", str(error), parent=self.window)
            else:
                messagebox.showerror("Действие не завершено", result, parent=self.window)
        self.window.after(100, self._poll)
