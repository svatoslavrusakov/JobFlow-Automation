"""Настройки ИИ берутся из общего файла; ключ и резюме читаются отдельно."""

from math import isfinite
from pathlib import Path

from core.settings_defaults import PROJECT_DIR, SETTINGS_FILE
from core.settings_store import load_settings as load_common_settings, resolve_path

# Совместимые стандартные пути; выбранные пути возвращает load_settings().
KEY_FILE = PROJECT_DIR / "data" / "ai_key.txt"


def read_text(path):
    """Не выводит содержимое файла, в том числе ключ, в сообщения об ошибках."""
    try:
        content = Path(path).read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Не удалось прочитать {path}.") from error
    if not content:
        raise ValueError(f"Файл {path} пуст.")
    return content


def load_settings(required_paths=("ai_key_file", "resume_file", "prompt_file")):
    values = load_common_settings()
    # Проверяем только ИИ: настройки браузера этому этапу не нужны.
    if values["ai_provider"] != "gemini" or not isinstance(values["ai_model"], str) or not values["ai_model"].strip():
        raise ValueError("Укажите Gemini и непустое имя модели в настройках.")
    for name in ("ai_max_rows", "ai_pause_every", "ai_pause_seconds"):
        if type(values[name]) is not int or values[name] < 1:
            raise ValueError(f"{name}: нужно положительное целое число.")
    # Распознавание HTML и ключевые слова не требуют пути к резюме.
    for name in required_paths:
        if not isinstance(values[name], str) or not values[name].strip():
            raise ValueError(f"Укажите путь: {name}.")
    timeout = values["timeouts"]["GEMINI_TIMEOUT"]
    if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
        raise ValueError("Ожидание Gemini: нужно положительное конечное число секунд.")
    return {
        "provider": values["ai_provider"],
        "model": values["ai_model"].strip(),
        "max_rows": values["ai_max_rows"],
        "pause_every": values["ai_pause_every"],
        "pause_seconds": values["ai_pause_seconds"],
        "key_file": resolve_path(values["ai_key_file"]),
        "resume_file": resolve_path(values["resume_file"]),
        "prompt_file": resolve_path(values["prompt_file"]),
        "requirements_prompt_file": resolve_path(values["requirements_prompt_file"]),
        "html_prompt_file": resolve_path(values["html_prompt_file"]),
        "timeout": values["timeouts"]["GEMINI_TIMEOUT"],
    }


def load_prompt(path=None, markers=("{{vacancy}}", "{{resume}}")):
    """Проверяет маркеры выбранного этапа; прежний формат письма сохранён."""
    path = path or load_settings()["prompt_file"]
    prompt = read_text(path)
    for marker in markers:
        if prompt.count(marker) != 1:
            raise ValueError(f"В шаблоне должен быть один маркер {marker}.")
    return prompt
