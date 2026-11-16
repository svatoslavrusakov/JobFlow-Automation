"""Общее чтение и сохранение настроек для окна и отдельных скриптов."""

import json
import math
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.settings_defaults import PROJECT_DIR, SETTINGS_FILE, default_settings


def resolve_path(value):
    """Относительные пути считаем от проекта, независимо от текущей папки."""
    path = Path(os.path.expandvars(str(value))).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Не удалось прочитать настройки: {path}.") from error


def load_settings():
    """До первого сохранения поддерживает прежний ai_settings.json."""
    values = default_settings()
    if SETTINGS_FILE.exists():
        saved = read_json(SETTINGS_FILE)
    else:
        saved = {}
        legacy = PROJECT_DIR / "data" / "ai_settings.json"
        if legacy.exists():
            old = read_json(legacy)
            if not isinstance(old, dict):
                raise ValueError("Старые настройки ИИ должны быть объектом JSON.")
            for old_key, new_key in (
                ("provider", "ai_provider"), ("model", "ai_model"),
                ("max_rows", "ai_max_rows"), ("pause_every", "ai_pause_every"),
                ("pause_seconds", "ai_pause_seconds"),
            ):
                if old_key in old:
                    saved[new_key] = old[old_key]
    if not isinstance(saved, dict) or set(saved) - set(values):
        raise ValueError("В файле настроек есть неизвестные параметры.")
    for name, value in saved.items():
        if name in ("delays", "timeouts"):
            if not isinstance(value, dict) or set(value) - set(values[name]):
                raise ValueError(f"Неверная группа настроек «{name}».")
            values[name].update(value)
        else:
            values[name] = value
    # Значения проверяет использующий их этап; неверная пауза ИИ не блокирует hh.
    return values


def check_timeout(value, name):
    """Проверяет только запрошенное ожидание до обращения к сервису."""
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: нужно положительное конечное число секунд.")
    if name == "CHROMEDRIVER_NETWORK_TIMEOUT" and not float(value).is_integer():
        raise ValueError(f"{name}: нужно целое число секунд.")
    return value


def validate_settings(values):
    """Проверяет значения до записи файлов или подключения к сервисам."""
    defaults = default_settings()
    if set(values) != set(defaults):
        raise ValueError("Набор параметров не соответствует настройкам программы.")
    for name, default in defaults.items():
        if isinstance(default, str) and (
            not isinstance(values[name], str) or not values[name].strip()
        ):
            raise ValueError(f"Заполните параметр «{name}».")
    if values["ai_provider"] != "gemini":
        raise ValueError("Сейчас поддерживается только Gemini.")
    address = values["chrome_address"].rsplit(":", 1)
    if len(address) != 2 or not address[0] or not address[1].isdigit() or not 1 <= int(address[1]) <= 65535:
        raise ValueError("Адрес Chrome: имя компьютера или IP и порт, например 127.0.0.1:9223.")
    for name in ("pages_to_scrape", "ai_max_rows", "ai_pause_every", "ai_pause_seconds"):
        if type(values[name]) is not int or values[name] < 1:
            raise ValueError(f"«{name}» должен быть положительным целым числом.")
    if not isinstance(values["blacklist"], list) or any(
        not isinstance(word, str) or not word.strip() for word in values["blacklist"]
    ):
        raise ValueError("Чёрный список должен содержать непустые слова.")
    if type(values["sound_enabled"]) is not bool:
        raise ValueError("Укажите, включён ли звуковой сигнал.")
    for group in ("delays", "timeouts"):
        if not isinstance(values[group], dict) or set(values[group]) != set(defaults[group]):
            raise ValueError(f"Неверный набор параметров «{group}».")
    for name, pair in values["delays"].items():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or any(
            type(number) not in (int, float) or not math.isfinite(number) for number in pair
        ) or not 0 <= pair[0] <= pair[1]:
            raise ValueError(f"{name}: нужны конечные числа 0 ≤ минимум ≤ максимум.")
    for name, number in values["timeouts"].items():
        check_timeout(number, name)


def write_private_file(path, text):
    """Записывает файл целиком: при обычной ошибке прежний файл сохраняется."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_settings(values):
    """В JSON хранятся пути к ключам, сами ключи сюда не передаются."""
    validate_settings(values)
    write_private_file(SETTINGS_FILE, json.dumps(values, ensure_ascii=False, indent=2) + "\n")


def restore_default_settings():
    """Сохраняет проблемный файл рядом как .bak и записывает стандартные настройки."""
    path = SETTINGS_FILE if SETTINGS_FILE.exists() else PROJECT_DIR / "data" / "ai_settings.json"
    backup = path.with_name(path.name + datetime.now().strftime(".%Y%m%d_%H%M%S_%f.bak"))
    path.rename(backup)
    try:
        save_settings(default_settings())
    except (OSError, ValueError):
        # Если запись не удалась, прежний файл остаётся на привычном месте.
        backup.rename(path)
        raise
    return backup
