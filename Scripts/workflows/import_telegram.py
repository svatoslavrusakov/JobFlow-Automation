"""JSON-экспорт Telegram → снимки для общих process-html, draft-html и import-results."""

from core import stop_control
from core.run_options import RunOptions
from core.settings_store import load_settings, resolve_path
from html_tools import html_storage
from telegram.export import normalize_channel, read_export, render_message


def import_messages(path, channel, directory, options):
    """Сохраняет каждый пост отдельно; повтор не заменяет снимки и готовые JSON."""
    channel = normalize_channel(channel)
    name, messages = read_export(path)
    saved = skipped = errors = 0
    print(f"Канал: {name}; записей в экспорте: {len(messages)}.")
    for number, message in enumerate(messages, start=1):
        stop_control.check()
        try:
            html = render_message(message, name)
            if html is None:
                skipped += 1
                continue
            url = f"{channel}/{message['id']}"
            if html_storage.has_snapshot(directory, url):
                skipped += 1
                continue
            # Формат снимка тот же, что у сайтов компаний; отдельного ИИ-конвейера нет.
            html_storage.save_snapshot(directory, url, url, html)
            saved += 1
            print(f"Сохранено сообщение: {url}")
        except (OSError, ValueError) as error:
            print(f"Запись {number}: {error}")
            errors += 1
            continue
        if options.limit is not None and saved >= options.limit:
            break
    print(f"Telegram: сохранено {saved}; пропущено {skipped}; ошибок {errors}.")
    if not messages:
        print("Экспорт пуст. Проверьте, содержит ли он нужные посты канала.")
    return 1 if errors else 0


def main(path, channel, options=None, data_dir=None):
    options = options or RunOptions()
    options.validate("import-telegram")
    try:
        directory = resolve_path(data_dir or load_settings()["telegram_dir"])
        return import_messages(resolve_path(path), channel, directory, options)
    except KeyboardInterrupt:
        print("Импорт Telegram остановлен. Сохранённые снимки остаются на диске.")
        return 130
    except (OSError, ValueError) as error:
        print(f"Импорт Telegram остановлен: {error}")
        return 1
