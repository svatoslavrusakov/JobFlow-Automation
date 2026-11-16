"""Общий звук до ручного закрытия проверки; не зависит от Selenium."""

import ctypes
import os

from core import config
from core import stop_control
from core.settings_store import resolve_path


def play_until_cleared(is_visible, sound_file=None):
    """Повторяет Duck.mp3, пока пользователь не закроет капчу в Chrome."""
    DUCK_FILE = resolve_path(sound_file or config.VALUES["sound_file"])
    if not config.VALUES["sound_enabled"]:
        return
    if not DUCK_FILE.is_file():
        print(f"Звуковой файл не найден: {DUCK_FILE}")
        return

    try:
        # MCI воспроизводит MP3 средствами Windows; отдельная библиотека не нужна.
        send = ctypes.WinDLL("winmm").mciSendStringW
        send.argtypes = (
            ctypes.c_wchar_p, ctypes.c_void_p,
            ctypes.c_uint, ctypes.c_void_p,
        )
        send.restype = ctypes.c_uint
    except (AttributeError, OSError) as error:
        print(f"Не удалось включить звуковой сигнал: {error}")
        return

    alias = f"hhDuck{os.getpid()}"
    code = send(f'open "{DUCK_FILE}" type mpegvideo alias {alias}', None, 0, None)
    if code:
        print(f"Не удалось открыть Duck.mp3 для воспроизведения (код {code}).")
        return

    try:
        # После каждого проигрывания смотрим, исчезло ли окно проверки.
        while is_visible():
            stop_control.check()
            code = send(f"play {alias} from 0 wait", None, 0, None)
            if code:
                print(f"Не удалось воспроизвести Duck.mp3 (код {code}).")
                break
    finally:
        send(f"close {alias}", None, 0, None)
