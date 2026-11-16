"""Привычная команда запуска; модули интерфейса находятся в ui/."""

import tkinter as tk
from tkinter import messagebox

from core.settings_store import load_settings, restore_default_settings


def recover_settings(error):
    """Предлагает восстановление; False означает отказ или ошибку записи."""
    window = tk.Tk()
    window.withdraw()
    try:
        if not messagebox.askyesno(
            "Настройки не загружены",
            f"{error}\n\nВосстановить стандартные настройки? "
            "Текущий файл будет сохранён рядом с расширением .bak.", parent=window,
        ):
            return False
        backup = restore_default_settings()
        messagebox.showinfo("Настройки восстановлены", f"Резервная копия: {backup}", parent=window)
        return True
    except (OSError, ValueError) as error:
        messagebox.showerror("Восстановление настроек", str(error), parent=window)
        return False
    finally:
        window.destroy()


def main():
    # Проверяем файл до импорта config: ошибку можно показать в отдельном окне.
    try:
        load_settings()
    except ValueError as error:
        if not recover_settings(error):
            return 1
    from ui.app import Application
    Application().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
