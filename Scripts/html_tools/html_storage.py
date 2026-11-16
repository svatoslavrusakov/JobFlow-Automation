"""Хранит снимки HTML и распознанные вакансии рядом с исходными страницами."""

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import urlsplit

from core.vacancy import normalize_vacancy


def get_snapshot_dir(output_dir, source_url):
    """Получает папку по полному исходному URL, включая параметры и фрагмент."""
    key = sha256(source_url.strip().encode("utf-8")).hexdigest()
    return Path(output_dir).resolve() / key


def read_snapshot(folder):
    """Читает ту же пару файлов, которую проверяет сборщик перед пропуском ссылки."""
    folder = Path(folder).resolve()
    try:
        source = json.loads((folder / "source.json").read_text(encoding="utf-8"))
        page = (folder / "page.html").read_bytes()
    except (OSError, ValueError) as error:
        raise ValueError(f"Не удалось прочитать снимок {folder}.") from error
    if not isinstance(source, dict) or (
        type(source.get("version")) is not int or source["version"] != 1
        or source.get("key") != folder.name
        or not isinstance(source.get("source_url"), str) or not source["source_url"].strip()
        or get_snapshot_dir(folder.parent, source["source_url"]) != folder
        or source.get("html_sha256") != sha256(page).hexdigest() or not page.strip()
        or not isinstance(source.get("final_url"), str) or not source["final_url"].strip()
        or not isinstance(source.get("saved_at"), str) or not source["saved_at"].strip()
    ):
        raise ValueError(f"Снимок повреждён или не соответствует ссылке: {folder}")
    # Повреждённые адреса отклоняем до обращения к модели.
    for field in ("source_url", "final_url"):
        address = urlsplit(source[field])
        if address.scheme not in ("http", "https") or not address.hostname:
            raise ValueError(f"В снимке нужен полный HTTP(S)-адрес: {field}.")
    try:
        return source, page.decode("utf-8")
    except UnicodeError:
        raise ValueError(f"HTML снимка должен быть в UTF-8: {folder}") from None


def has_snapshot(output_dir, source_url):
    """Проверяет готовый снимок; повреждённую папку не считаем готовой."""
    folder = get_snapshot_dir(output_dir, source_url)
    if not folder.exists():
        return False
    source, _ = read_snapshot(folder)
    if source["source_url"] != source_url.strip():
        raise ValueError(f"Снимок не соответствует ссылке: {folder}")
    return True


def save_snapshot(output_dir, source_url, final_url, html):
    """Публикует готовую пару файлов, сохраняя существующие снимки."""
    if not html.strip() or not final_url.strip():
        raise ValueError("Нельзя сохранить пустой HTML или конечный адрес.")
    folder = get_snapshot_dir(output_dir, source_url)
    folder.parent.mkdir(parents=True, exist_ok=True)
    if folder.exists():
        raise FileExistsError(f"Папка снимка уже существует: {folder}")
    page = html.encode("utf-8")
    source = {
        "version": 1, "key": folder.name,
        "source_url": source_url.strip(), "final_url": final_url,
        # Это локальное время снимка, не время отправки отклика.
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "html_sha256": sha256(page).hexdigest(),
    }
    # Переименование публикует оба файла сразу; существующий снимок не заменяем.
    with TemporaryDirectory(prefix=".capture-", dir=folder.parent) as temporary:
        staging = Path(temporary)
        (staging / "page.html").write_bytes(page)
        (staging / "source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(folder)
    return folder


def read_vacancy(folder, source):
    """Готовый результат пропускаем, повреждённый сохраняем для ручной проверки."""
    path = Path(folder) / "vacancy.json"
    if not path.exists():
        return None
    vacancy = normalize_vacancy(json.loads(path.read_text(encoding="utf-8")))
    if vacancy["ID"] != "site:" + source["key"] or vacancy["Ссылка"] != source["source_url"]:
        raise ValueError("vacancy.json не соответствует исходной ссылке.")
    return vacancy


def save_vacancy(folder, vacancy):
    """Сначала готовит полный JSON во временном файле; прежний результат не заменяет."""
    return save_json(Path(folder) / "vacancy.json", normalize_vacancy(vacancy))


def save_json(path, values):
    """Публикует полный JSON одним переименованием, не заменяя прежний результат."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path.name} уже существует.")
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(values, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        # В Windows rename не перезаписывает существующий файл.
        temporary.rename(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
