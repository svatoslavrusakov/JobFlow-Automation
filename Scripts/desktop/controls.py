"""Наведение, клик и ввод Unicode в активное окно обычного Chrome."""

import time
from uuid import uuid4

from core import stop_control
from core import utils


class Controls:
    def __init__(self, window, interval):
        # Эти библиотеки нужны только запущенному экранному режиму.
        import pyautogui
        import pyperclip
        from pynput.keyboard import Controller
        self.mouse, self.clipboard = pyautogui, pyperclip
        self.keyboard = Controller()
        self.window, self.interval = window, interval
        self.target_point = self.target_bounds = None
        self.mouse.FAILSAFE = True
        self.mouse.PAUSE = 0.1

    def check(self):
        self.window.check()
        try:
            self.mouse.failSafeCheck()
        except self.mouse.FailSafeException:
            raise KeyboardInterrupt from None

    def pause(self, seconds):
        deadline = time.monotonic() + seconds
        while True:
            self.check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            stop_control.pause(min(0.2, remaining))

    def delay(self, setting):
        utils.human_delay(setting, wait=self.pause)

    def _mouse_action(self, action, *args, **kwargs):
        self.check()
        try:
            return action(*args, **kwargs)
        except self.mouse.FailSafeException:
            raise KeyboardInterrupt from None

    def hotkey(self, *keys):
        # После работы с клавиатурой прежняя цель клика больше не подтверждена.
        self.target_point = self.target_bounds = None
        self._mouse_action(self.mouse.hotkey, *keys)
        self.check()

    def move_to(self, box):
        """Наводит курсор на центр элемента; box задан относительно Chrome."""
        self.check()
        bounds = self.window.bounds()
        left, top, width, height = box
        x, y, window_width, window_height = bounds
        if min(left, top) < 0 or min(width, height) <= 0 or left + width > window_width or top + height > window_height:
            raise RuntimeError("Цель наведения выходит за границы Chrome.")
        point = (x + left + width // 2, y + top + height // 2)
        self._mouse_action(self.mouse.moveTo, *point, duration=0.25)
        self.check()
        self.target_point, self.target_bounds = point, bounds
        return point

    def click_at(self, point):
        """Нажимает в уже подтверждённой точке, не перемещая курсор повторно."""
        self.check()
        if self.target_point != point or self.target_bounds != self.window.bounds():
            raise RuntimeError("Цель клика или положение Chrome изменились.")
        if tuple(self.mouse.position()) != point:
            raise RuntimeError("Курсор переместился после наведения. Клик отменён.")
        # Один раз навели и подтвердили — один клик. Автоматического повтора нет.
        self.target_point = self.target_bounds = None
        self._mouse_action(self.mouse.click)
        self.check()

    def read_selection(self):
        """Копирует выделенный текст; прежний текст буфера возвращает обратно."""
        previous = self.clipboard.paste()
        marker = uuid4().hex
        try:
            self.clipboard.copy(marker)
            self.hotkey("ctrl", "c")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                self.check()
                value = self.clipboard.paste()
                if value != marker:
                    return value
                stop_control.pause(0.05)
            raise RuntimeError("Не удалось прочитать выделенный текст.")
        finally:
            self.clipboard.copy(previous)

    def read_url(self):
        self.hotkey("ctrl", "l")
        try:
            return self.read_selection().strip()
        finally:
            self.hotkey("esc")

    def require_vacancy(self, item):
        actual_id, _ = utils.parse_vacancy_link(self.read_url())
        if actual_id != item["id"]:
            raise RuntimeError("В Chrome открыта другая вакансия. Действие отменено.")

    def open_vacancy(self, item):
        self.hotkey("ctrl", "l")
        self.keyboard.type(item["link"])
        self.hotkey("enter")

    def verify_letter(self, text):
        """Только читает выделенный текст; при потере фокуса отправку отменяет."""
        self.hotkey("ctrl", "a")
        actual = self.read_selection().replace("\r\n", "\n").replace("\r", "\n")
        self.hotkey("right")
        if actual != text:
            raise RuntimeError("Текст в поле не совпал с письмом. Отправка отменена.")

    def type_letter(self, text, check_page):
        """False означает появившуюся анкету; другие изменения останавливают запуск."""
        if any(ord(char) < 32 and char != "\n" for char in text):
            raise ValueError("В письме есть управляющие символы. Уберите их перед вводом.")
        if not check_page():
            return False
        self.hotkey("ctrl", "a")
        next_check = time.monotonic() + 0.5
        for char in text:
            self.check()
            # Снимок перед каждым символом перегружал бы слабый ПК.
            # Проверяем страницу периодически и перед переводом строки.
            if char == "\n" or time.monotonic() >= next_check:
                if not check_page():
                    return False
                next_check = time.monotonic() + 0.5
            if char == "\n":
                from pynput.keyboard import Key
                self.keyboard.tap(Key.enter)
            else:
                self.keyboard.type(char)
            self.pause(self.interval)
        if not check_page():
            return False
        self.verify_letter(text)
        return True
