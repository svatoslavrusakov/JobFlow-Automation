"""Два локальных этапа: распознать HTML или подготовить письмо по vacancy.json."""

from ai import html_draft, html_vacancy, pacing, settings
from core import stop_control
from core.run_options import RunOptions
from core.settings_store import load_settings, resolve_path
from html_tools import html_storage


def process_snapshot(folder, source, html, options, template):
    """Распознаёт одну вакансию и проверяет неизменность источника перед записью."""
    vacancy = html_vacancy.extract_vacancy(html, source, options, template)
    current, _ = html_storage.read_snapshot(folder)
    if current != source:
        raise ValueError("Снимок изменился во время распознавания; запись отменена.")
    stop_control.check()
    return html_storage.save_vacancy(folder, vacancy)


def read_pending(folder, source, html, command):
    """Возвращает вход этапа; None — готово, нет входа или снимок отложен."""
    error_file = folder / f"{command}.error.json"
    if error_file.exists():
        print(f"Снимок {folder.name}: отложен; для повтора удалите {error_file.name}.")
        return None
    vacancy = html_storage.read_vacancy(folder, source)
    if command == "process-html":
        return html if vacancy is None else None
    if vacancy is None:
        return None  # Сначала нужно распознать HTML; модель для этой папки не вызывается.
    return vacancy if html_draft.read_draft(folder, vacancy) is None else None


def load_model_input(command):
    """Распознавание не требует резюме; подготовка письма использует обычный промпт."""
    if command == "process-html":
        options = settings.load_settings(required_paths=("ai_key_file", "html_prompt_file"))
        template = settings.load_prompt(options["html_prompt_file"], markers=("{{html}}", "{{url}}"))
        resume = None
    else:
        options = settings.load_settings()
        template = settings.load_prompt(options["prompt_file"])
        resume = settings.read_text(options["resume_file"])
    settings.read_text(options["key_file"])
    return options, template, resume


def process_snapshots(options, command="process-html", data_dir=None):
    """Общая очередь, паузы и лимит для двух последовательных файловых этапов."""
    values = load_settings()
    directory = resolve_path(data_dir or values["html_dir"])
    if not directory.is_dir():
        raise ValueError("Папка HTML-снимков не найдена. Сначала сохраните страницы или импортируйте сообщения.")
    folders = sorted(path for path in directory.iterdir() if path.is_dir() and not path.name.startswith("."))
    if not folders:
        print("В папке нет HTML-снимков для обработки.")
        return 0
    ai_options = template = resume = None
    processed = saved = skipped = errors = 0
    for folder in folders:
        stop_control.check()
        try:
            source, html = html_storage.read_snapshot(folder)
            pending = read_pending(folder, source, html, command)
            if pending is None:
                skipped += 1
                continue
        except (OSError, ValueError) as error:
            print(f"Снимок {folder.name}: {error}")
            errors += 1
            continue
        # Настройки модели и ключ читаем только перед первым новым запросом.
        if ai_options is None:
            ai_options, template, resume = load_model_input(command)
        pacing.pause_before(processed, ai_options)
        processed += 1
        print(f"{command}: снимок {folder.name}.")
        try:
            if command == "process-html":
                path = process_snapshot(folder, source, pending, ai_options, template)
            else:
                path = html_draft.create_draft(folder, source, pending, ai_options, template, resume)
        except (ValueError, OSError) as error:
            print(f"Снимок {folder.name}: результат не сохранён: {error}")
            if isinstance(error, ValueError):
                # Ошибочный ответ не должен занимать малый лимит при каждом запуске.
                marker = folder / f"{command}.error.json"
                html_storage.save_json(marker, {"error": str(error)})
                print(f"Отложен. Для повторной попытки удалите {marker}.")
            errors += 1
        else:
            saved += 1
            print(f"Сохранено: {path}")
        limit = options.limit if options.limit is not None else ai_options["max_rows"]
        if processed >= limit:
            break
    print(f"HTML: сохранено {saved}; пропущено готовых/отложенных/без входа {skipped}; ошибок {errors}.")
    return 1 if errors else 0


def main(options=None, command="process-html", data_dir=None):
    options = options or RunOptions()
    if command not in ("process-html", "draft-html"):
        raise ValueError("Неизвестный этап обработки HTML.")
    options.validate(command)
    try:
        return process_snapshots(options, command, data_dir)
    except KeyboardInterrupt:
        print("ИИ-обработка остановлена. Сохранённые JSON остаются в папках снимков.")
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        # Ошибка API останавливает запуск: следующие страницы не расходуют квоту.
        print(f"ИИ-обработка HTML остановлена: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
