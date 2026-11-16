"""Готовит один локальный черновик резюме; Google Таблицу не изменяет."""

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp

from core import utils
from ai import draft, gateway, settings
from ai.resume_result import RESUME_SCHEMA, parse_resume
from core.settings_defaults import PROJECT_DIR
from core.settings_store import write_private_file

PROMPT_FILE = Path(__file__).with_name("resume_prompt.txt")
OUTPUT_DIR = PROJECT_DIR / "data" / "resume_drafts"
SOURCE_FIELDS = ("ID", "Ссылка", "Заголовок", "Компания", "Зарплата", "Описание")


def check_vacancy(vacancy):
    """Проверяет вход до обращения к модели."""
    for field in SOURCE_FIELDS:
        if vacancy.get(field, "").lstrip().startswith("="):
            raise ValueError(f"Резюме: в поле «{field}» находится формула.")
    vacancy_id, _ = utils.parse_vacancy_link(vacancy.get("Ссылка", ""))
    if vacancy.get("ID", "").strip() not in ("", vacancy_id):
        raise ValueError("Резюме: ID не совпадает со ссылкой.")
    if not vacancy.get("Заголовок", "").strip() or not vacancy.get("Описание", "").strip():
        raise ValueError("Резюме: нужны заголовок и описание вакансии.")
    return vacancy_id


def create_resume_draft(vacancy):
    """Использует общие модель, ключ и исходное резюме, возвращает путь к JSON."""
    vacancy = dict(vacancy)
    vacancy_id = check_vacancy(vacancy)
    options = settings.load_settings()
    original = settings.read_text(options["resume_file"])
    template = settings.load_prompt(PROMPT_FILE)
    prompt = draft.build_prompt(vacancy, original, template)
    answer = gateway.generate(prompt, options, schema=RESUME_SCHEMA)
    adapted = parse_resume(answer, original)
    # Метаданные задаёт программа, а не модель. Каждый результат требует ручной проверки.
    source = {field: vacancy.get(field, "") for field in SOURCE_FIELDS}
    document = {
        "version": 1,
        "review_status": "needs_review",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "vacancy": source,
        "model": options["model"],
        "source_resume_sha256": sha256(original.encode("utf-8")).hexdigest(),
        "resume": adapted,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Отдельная уникальная папка сохраняет предыдущие варианты этой же вакансии.
    output = Path(mkdtemp(prefix=f"{vacancy_id}_", dir=OUTPUT_DIR)) / "resume.json"
    write_private_file(output, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return output
