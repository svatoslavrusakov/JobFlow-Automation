"""Письмо из локального vacancy.json: тот же генератор и формат ответа, что у hh."""

import json
from datetime import datetime
from pathlib import Path

from ai import draft, result
from core import stop_control
from html_tools import html_storage


def read_draft(folder, vacancy):
    """Пропускает готовое письмо; изменённый источник требует ручного решения."""
    path = Path(folder) / "draft.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("vacancy") != vacancy:
        raise ValueError("draft.json не соответствует vacancy.json.")
    # Повторно применяем проверку письма, оценки, рисков и цитат из описания.
    data["result"] = result.parse_result(json.dumps(data.get("result")), vacancy["Описание"])
    return data


def create_draft(folder, source, vacancy, options, template, resume):
    """Готовит письмо без браузера; исходники сверяются после ответа модели."""
    answer = draft.create_draft(vacancy, resume, options, template)
    current_source, _ = html_storage.read_snapshot(folder)
    current_vacancy = html_storage.read_vacancy(folder, source)
    if current_source != source or current_vacancy != vacancy:
        raise ValueError("Исходник изменился во время генерации; запись отменена.")
    stop_control.check()
    # Вакансия внутри документа связывает письмо с конкретной версией описания.
    # Резюме и ключ сюда не копируем. Таблица и статус на этом этапе не меняются.
    values = {
        "vacancy": vacancy, "result": answer, "model": options["model"],
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return html_storage.save_json(Path(folder) / "draft.json", values)
