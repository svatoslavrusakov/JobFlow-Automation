"""Распознаёт образцы и повторно проверяет цель после наведения курсора."""

import time

from core import stop_control
from desktop.profile import check_template, template_path

STATUS_MARKERS = {
    "wait": "wait", "delivered": "wait", "reject": "reject",
    "invite": "invite", "archive": "archive", "unavailable": "unavailable",
}
ACTION_MARKERS = {"apply", "dialog", "resume", "letter", "add_letter", "submit"}


class Screen:
    def __init__(self, window, profile):
        import cv2
        import numpy as np
        self.cv, self.np = cv2, np
        self.window, self.profile = window, profile
        self.templates = {}
        for kind, names in profile["templates"].items():
            images = []
            for name in names:
                # imdecode поддерживает кириллицу в пути Windows.
                raw = np.fromfile(str(template_path(name)), dtype=np.uint8)
                image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                check_template(image, name)
                images.append(image)
            self.templates[kind] = images
        self.image = self.origin = None

    def take(self):
        self.window.require_geometry(self.profile)
        bounds = self.window.bounds()
        image = self.window.capture()
        if bounds != self.window.bounds():
            raise RuntimeError("Chrome переместился во время снимка. Действие отменено.")
        self.origin = bounds[:2]
        self.image = self.cv.cvtColor(self.np.array(image), self.cv.COLOR_RGB2BGR)

    def _area(self, dialog, near):
        """Ограничивает поиск окном отклика и прежней областью элемента."""
        height, width = self.image.shape[:2]
        x, y = 0, 0
        if dialog:
            x, y, width, height = self.profile["dialog_area"]
        right, bottom = x + width, y + height
        if near is not None:
            left, top, old_width, old_height = near
            # Небольшой сдвиг допустим, но соседняя одинаковая кнопка не подойдёт.
            x, y = max(x, left - 12), max(y, top - 12)
            right, bottom = min(right, left + old_width + 12), min(bottom, top + old_height + 12)
        return x, y, self.image[y:max(y, bottom), x:max(x, right)]

    def _matches(self, template, area, active):
        """Возвращает отдельные совпадения одного образца."""
        height, width = template.shape[:2]
        if height > area.shape[0] or width > area.shape[1]:
            return
        scores = self.cv.matchTemplate(area, template, self.cv.TM_CCOEFF_NORMED)
        while True:
            # Даже неудачный образец не должен лишать пользователя остановки.
            self.window.check()
            _, score, _, point = self.cv.minMaxLoc(scores)
            if score < self.profile["confidence"]:
                return
            left, top = point
            scores[max(0, top-height//2):top+height//2+1, max(0, left-width//2):left+width//2+1] = -1
            # Затемнённая кнопка под всплывшим окном не годится для действия.
            patch = area[top:top + height, left:left + width]
            if active and self.np.abs(patch.astype("float32") - template).mean() > 18:
                continue
            yield left, top, width, height

    def find(self, name, dialog=False, unique=True, near=None):
        """Возвращает прямоугольник относительно Chrome в текущем снимке."""
        if self.image is None:
            raise RuntimeError("Сначала нужен снимок экрана.")
        x, y, area = self._area(dialog, near)
        if area.size == 0:
            return None
        found = []
        for template in self.templates.get(name, []):
            for left, top, width, height in self._matches(template, area, name in ACTION_MARKERS):
                box = (left + x, top + y, width, height)
                if not any(abs(box[0]-old[0]) < width//2 and abs(box[1]-old[1]) < height//2 for old in found):
                    found.append(box)
                if len(found) > 1:
                    if unique:
                        raise RuntimeError(f"Найдено несколько элементов «{name}». Уточните образец.")
                    return found[0]
        return found[0] if found else None

    def guard(self):
        if self.find("captcha", unique=False):
            from core.sound_alarm import play_until_cleared
            print("Распознана капча. Пройдите её вручную; запуск после этого завершится.")
            def visible():
                self.take()
                return self.find("captcha", unique=False) is not None
            play_until_cleared(visible)
            raise PermissionError("Распознана проверка пользователя. Повторите запуск после её прохождения.")
        return "form" if self.find("form", unique=False) else None

    def require_dialog(self):
        if not self.find("dialog", dialog=True) or not self.find("resume", dialog=True):
            raise RuntimeError("Окно отклика или выбранное резюме не подтверждены.")

    def check_letter_dialog(self):
        """Свежая проверка страницы до ввода и периодически во время печати."""
        self.take()
        if self.guard() == "form":
            return False
        self.require_dialog()
        return True

    def confirm_target(self, name, point, old_box, dialog=False):
        """Подтверждает ту же цель под курсором по новому снимку."""
        self.take()
        if self.guard() == "form":
            return False
        if dialog:
            self.require_dialog()
        box = self.find(name, dialog=dialog, near=old_box)
        if box is None:
            raise RuntimeError(f"Элемент «{name}» исчез после наведения. Клик отменён.")
        left, top, width, height = box
        x, y = point[0] - self.origin[0], point[1] - self.origin[1]
        if not (left <= x < left + width and top <= y < top + height):
            raise RuntimeError("Элемент сместился из-под курсора. Клик отменён.")
        return True

    def status(self):
        found = {value for marker, value in STATUS_MARKERS.items() if self.find(marker, unique=False)}
        responses = found & {"reject", "invite"}
        if len(responses) > 1:
            raise RuntimeError("На экране противоречивые ответы работодателя.")
        if responses:
            return responses.pop()
        return next((x for x in ("archive", "unavailable", "wait") if x in found), None)

    def wait(self, names, timeout, dialog=False):
        deadline = time.monotonic() + timeout
        while True:
            self.take()
            if self.guard() == "form":
                return "form", None
            for name in names:
                box = self.find(name, dialog=dialog, unique=name not in STATUS_MARKERS)
                if box:
                    return name, box
            if time.monotonic() >= deadline:
                raise RuntimeError("Знакомый экран не появился. Проверьте Chrome и образцы.")
            stop_control.pause(0.5)
