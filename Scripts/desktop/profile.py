"""Образцы элементов и параметры одного экрана хранятся только в data."""

import json
import math
from pathlib import Path

from core.settings_defaults import PROJECT_DIR
from core.settings_store import write_private_file

DIRECTORY = PROJECT_DIR / "data" / "desktop"
PROFILE_FILE = DIRECTORY / "profile.json"

# Название, подсказка для выделения образца.
MARKERS = {
    "dialog_area": ("Область окна отклика", "Выделите целиком развёрнутое окно отклика вместе с кнопкой отправки."),
    "dialog": ("Заголовок окна отклика", "Заголовок «Отклик на вакансию» внутри окна."),
    "resume": ("Выбранное резюме", "Название уже выбранного резюме внутри окна."),
    "letter": ("Пустое поле письма", "Подпись внутри пустого поля; центр образца должен попадать в поле ввода."),
    "add_letter": ("Добавить сопроводительное", "Кнопка, раскрывающая поле письма; необязательный образец."),
    "submit": ("Финальная кнопка", "Активная кнопка целиком после ручного заполнения письма. Не нажимайте её."),
    "apply": ("Кнопка на странице", "Первичная кнопка «Откликнуться» целиком, включая фон и границы."),
    "wait": ("Уже откликнулись", "Ярлык «Вы откликнулись» рядом с действиями вакансии."),
    "delivered": ("Резюме доставлено", "Подтверждение доставки рядом с действиями вакансии."),
    "form": ("Анкета работодателя", "Характерный заголовок анкеты работодателя, не окно выбора города."),
    "captcha": ("Проверка пользователя", "Характерная надпись капчи. Решение капчи программа не выполняет."),
    "archive": ("Архив", "Сообщение, что вакансия в архиве."),
    "unavailable": ("Недоступная вакансия", "Сообщение «Вам недоступна эта вакансия»."),
    "reject": ("Отказ", "Ярлык «Вам отказали» рядом с действиями вакансии."),
    "invite": ("Приглашение", "Ярлык «Вас пригласили» рядом с действиями вакансии."),
}


def default_profile():
    return {
        "screen_size": [], "window_size": [], "dialog_area": [],
        "confidence": 0.94, "typing_interval": 0.06, "countdown": 8,
        "templates": {},
    }


def load_profile():
    values = default_profile()
    if PROFILE_FILE.exists():
        try:
            saved = json.loads(PROFILE_FILE.read_text(encoding="utf-8-sig"))
            if not isinstance(saved, dict) or set(saved) - set(values):
                raise ValueError
            values.update(saved)
        except (OSError, ValueError) as error:
            raise ValueError("Не удалось прочитать data/desktop/profile.json.") from error
    # Проверяем структуру до создания вкладки; неполная калибровка пока допустима.
    validate(values, ready=False)
    return values


def save_profile(values):
    validate(values, ready=False)
    write_private_file(PROFILE_FILE, json.dumps(values, ensure_ascii=False, indent=2) + "\n")


def template_path(name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".png"):
        raise ValueError("Неверное имя образца экрана.")
    return DIRECTORY / name


def check_template(image, name="образец"):
    """Один и тот же контроль при сохранении образца и при его загрузке."""
    import numpy as np
    array = np.asarray(image)
    if array.ndim not in (2, 3) or min(array.shape[:2]) < 12:
        raise ValueError(f"{name}: нужен фрагмент хотя бы 12×12 пикселей.")
    pixels = array.reshape(-1, array.shape[2] if array.ndim == 3 else 1)
    # Считаем различия пикселей внутри каналов: однотонный синий тоже не подходит.
    if pixels.std(axis=0).max() < 5:
        raise ValueError(f"{name}: выделите текст или различимый элемент, а не однотонный фон.")


def validate(values, ready=True, submit=False):
    if not isinstance(values, dict) or set(values) != set(default_profile()):
        raise ValueError("Неверный набор параметров калибровки.")
    for key, lower, upper in (
        ("confidence", 0.85, 1.0), ("typing_interval", 0.02, 1.0), ("countdown", 3, 60),
    ):
        value = values[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{key}: допустимо от {lower} до {upper}.")
    for key, length in (("screen_size", 2), ("window_size", 2), ("dialog_area", 4)):
        value = values[key]
        if value == [] and not ready:
            continue
        if not isinstance(value, list) or len(value) != length or any(type(x) is not int or x < 0 for x in value):
            raise ValueError(f"Неверная область калибровки: {key}. Сохраните её заново.")
        if min(value[-2:]) <= 0:
            raise ValueError(f"Размер области {key} должен быть положительным.")
    if values["dialog_area"]:
        x, y, width, height = values["dialog_area"]
        if not values["window_size"] or width < 20 or height < 20 or x + width > values["window_size"][0] or y + height > values["window_size"][1]:
            raise ValueError("Область окна отклика выходит за границы Chrome.")
    templates = values["templates"]
    if not isinstance(templates, dict) or set(templates) - (set(MARKERS) - {"dialog_area"}):
        raise ValueError("Неверный список образцов экрана.")
    for names in templates.values():
        if not isinstance(names, list) or not names:
            raise ValueError("Для элемента нужен непустой список PNG-образцов.")
        for name in names:
            path = template_path(name)
            if ready and not path.is_file():
                raise ValueError(f"Нет файла образца: {name}.")
    if not ready:
        return
    required = ["dialog", "resume", "letter"]
    if submit:
        required += ["submit", "apply", "form", "captcha"]
        if not any(templates.get(name) for name in ("wait", "delivered")):
            required.append("wait")
    missing = [MARKERS[name][0] for name in required if not templates.get(name)]
    if missing:
        raise ValueError("Добавьте образцы: " + ", ".join(missing))
