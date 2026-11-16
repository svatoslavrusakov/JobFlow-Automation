"""Общая пауза перед очередным запросом ИИ; готовые записи её не вызывают."""

from core import stop_control


def pause_before(processed, options):
    """processed — число выполненных попыток, включая неверный ответ модели."""
    if processed and processed % options["pause_every"] == 0:
        seconds = options["pause_seconds"]
        print(f"Пауза после {processed} попыток ИИ-обработки: {seconds} с")
        stop_control.pause(seconds)
