"""Останавливает этап по запросу локального интерфейса между действиями."""

import os
import time
from pathlib import Path


def check():
    """Прерывает запуск, если окно запросило остановку."""
    path = os.environ.get("AUTO_HH_STOP_FILE")
    if path and Path(path).exists():
        raise KeyboardInterrupt


def pause(seconds):
    """Ждёт между строками и проверяет запрос остановки каждые 0,5 с."""
    if not os.environ.get("AUTO_HH_STOP_FILE"):
        time.sleep(seconds)
        return

    deadline = time.monotonic() + seconds
    while True:
        check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))
