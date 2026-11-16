"""Экспорт проверенного JSON в DOCX-черновик для ручной правки."""

import json
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from ai.resume import SOURCE_FIELDS
from ai.resume_result import parse_resume
from ai.settings import read_text
from core.settings_store import load_settings, resolve_path


def read_draft(json_file, vacancy=None):
    """Проверяет исходник и, если передана вакансия, принадлежность черновика."""
    data = json.loads(Path(json_file).read_text(encoding="utf-8-sig"))
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
    ):
        raise ValueError("Неподдерживаемый формат черновика резюме.")
    if vacancy is not None:
        # Статус и письмо могут меняться; сверяем только входные данные генерации.
        expected = {field: vacancy.get(field, "") for field in SOURCE_FIELDS}
        if data.get("vacancy") != expected:
            raise ValueError("Черновик создан для другой вакансии или её данные изменились.")
    original = read_text(resolve_path(load_settings()["resume_file"]))
    if sha256(original.encode("utf-8")).hexdigest() != data.get("source_resume_sha256"):
        raise ValueError("Исходное резюме изменилось. Выберите нужный исходник или создайте новый черновик.")
    return parse_resume(json.dumps(data.get("resume"), ensure_ascii=False), original)


def build_document(data):
    """Задаёт базовое оформление; точный шаблон подключим после его получения."""
    try:
        from docx import Document
        from docx.shared import Cm, Pt, RGBColor
    except ImportError:
        raise ValueError("Для экспорта установите зависимости с python-docx.") from None
    document = Document()
    page = document.sections[0]
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.top_margin = page.bottom_margin = Cm(2)
    page.left_margin = page.right_margin = Cm(2)
    for name, size in (("Normal", 11), ("Heading 1", 13)):
        style = document.styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
    document.styles["Heading 1"].paragraph_format.keep_with_next = True
    document.core_properties.author = ""
    sections = {section["title"]: section for section in data["sections"]}
    order = ("Контакты", "О себе", "Навыки", "Опыт работы", "Образование", "Дополнительно")
    for title in order:
        if title not in sections:
            continue
        document.add_heading(title, level=1)
        style = "List Bullet" if title in ("Навыки", "Опыт работы") else "Normal"
        for item in sections[title]["items"]:
            # Цитаты, вопросы и пояснения остаются в JSON для проверки.
            document.add_paragraph(item["text"], style=style)
    return document


def create_docx(json_file, vacancy=None):
    """Каждый экспорт получает отдельный файл рядом с исходным JSON."""
    json_file = Path(json_file)
    # Проверяем файл заново: после выбора пользователь мог изменить JSON или исходник.
    document = build_document(read_draft(json_file, vacancy=vacancy))
    stream = NamedTemporaryFile(
        dir=json_file.parent, prefix="resume_draft_", suffix=".docx", delete=False,
    )
    output = Path(stream.name)
    try:
        with stream:
            document.save(stream)
    except BaseException:
        # Удаляем только созданный этой функцией незавершённый файл.
        output.unlink(missing_ok=True)
        raise
    return output
