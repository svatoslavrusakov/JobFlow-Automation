"""Проверка активного Chrome средствами Windows, без WebDriver и CDP."""

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from core import stop_control


class ChromeWindow:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Экранный режим сейчас поддерживает только Windows.")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user.SetProcessDPIAware()  # Координаты и снимки в физических пикселях.
        # HWND и HANDLE имеют размер указателя, в том числе в 64-битном Python.
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.IsZoomed.argtypes = [wintypes.HWND]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.hwnd = self.user.GetForegroundWindow()
        self._require_chrome()
        self.size = self.bounds()[2:]

    def _require_chrome(self):
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        handle = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            raise RuntimeError("Не удалось определить приложение активного окна.")
        try:
            text, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
                raise RuntimeError("Не удалось прочитать имя активного приложения.")
            if Path(text.value).name.casefold() != "chrome.exe":
                raise RuntimeError("Перед началом переключитесь в нужное окно Google Chrome.")
        finally:
            self.kernel.CloseHandle(handle)

    def bounds(self):
        rect, point = wintypes.RECT(), wintypes.POINT(0, 0)
        if not self.user.GetClientRect(self.hwnd, ctypes.byref(rect)) or not self.user.ClientToScreen(self.hwnd, ctypes.byref(point)):
            raise RuntimeError("Не удалось прочитать границы Chrome.")
        left, top, right, bottom = point.x, point.y, point.x + rect.right, point.y + rect.bottom
        if self.user.IsZoomed(self.hwnd):
            # У развёрнутого окна рамка Windows может иметь координаты -8, -8.
            # Снимаем только видимые пиксели основного монитора.
            left, top = max(0, left), max(0, top)
            right = min(self.user.GetSystemMetrics(0), right)
            bottom = min(self.user.GetSystemMetrics(1), bottom)
        if right <= left or bottom <= top:
            raise RuntimeError("Разместите Chrome на основном мониторе.")
        return left, top, right - left, bottom - top

    def check(self):
        stop_control.check()
        if self.user.GetAsyncKeyState(0x1B) & 0x8000:
            raise KeyboardInterrupt
        if self.user.GetForegroundWindow() != self.hwnd:
            raise RuntimeError("Активное окно изменилось. Экранный запуск остановлен.")
        if self.bounds()[2:] != self.size:
            raise RuntimeError("Размер Chrome изменился. Нужна повторная калибровка.")

    def capture(self):
        from PIL import ImageGrab
        self.check()
        x, y, width, height = self.bounds()
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        self.check()
        return image

    def require_geometry(self, profile):
        self.check()
        actual = (self.user.GetSystemMetrics(0), self.user.GetSystemMetrics(1))
        if list(actual) != profile["screen_size"] or list(self.size) != profile["window_size"]:
            raise RuntimeError("Размер экрана или Chrome отличается от сохранённых образцов.")
        x, y, width, height = self.bounds()
        if x < 0 or y < 0 or x + width > actual[0] or y + height > actual[1]:
            raise RuntimeError("Разместите Chrome целиком на основном мониторе.")
