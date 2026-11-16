# utils.py
import math
import time
import random
import re
from urllib.parse import urlsplit

from core import config
from core import stop_control
from core.settings_store import check_timeout

def human_delay(delay_settings, announce=True, cancelable=False, wait=None):
    """Выполняет паузу; короткие промежуточные паузы можно не печатать."""
    # В настройке — минимум, максимум в секундах и пояснение.
    min_sec, max_sec, reason = delay_settings

    delay = random.uniform(min_sec, max_sec)
    # Округляем только вывод; длительность ожидания сохраняется.
    if announce:
        print(f"Пауза {reason}: {delay:.1f} с")
    # Внутри активного отклика паузу не прерываем; между строками можно.
    if wait is not None:
        # Экранный режим проверяет Escape и активное окно даже во время паузы.
        wait(delay)
    elif cancelable:
        stop_control.pause(delay)
    else:
        time.sleep(delay)

def get_vacancy_id(url):
    """Извлекает ID вакансии из ссылки"""
    # ID остаётся строкой для сравнения со значениями из Google Sheets.
    match = re.search(r'/vacancy/(\d+)', url)
    return match.group(1) if match else None


def is_hh_host(host):
    """Проверяет основной домен hh и его региональные поддомены."""
    return any(
        host == domain or host.endswith("." + domain)
        for domain in ("hh.ru", "hh.kz")
    )


def parse_vacancy_link(link):
    """Проверяет ссылку и возвращает ID и очищенный адрес."""
    # Разбираем адрес отдельно на протокол, домен, путь и параметры.
    parts = urlsplit(link.strip())
    hostname = parts.hostname or ""

    if parts.scheme not in ("http", "https"):
        raise ValueError("Ссылка должна начинаться с http:// или https://.")

    # Разрешаем только проверенные домены и их региональные поддомены.
    if not is_hh_host(hostname):
        raise ValueError("Нужна ссылка на вакансию hh.ru или hh.kz.")

    vacancy_id = get_vacancy_id(parts.path)

    # Проверяем весь путь: ссылка должна вести именно на вакансию.
    if not vacancy_id or parts.path.rstrip("/") != f"/vacancy/{vacancy_id}":
        raise ValueError("В ссылке не найден корректный адрес вакансии.")

    # Заново собираем адрес без параметров поиска и фрагмента после #.
    clean_link = f"https://{hostname}/vacancy/{vacancy_id}"
    # Возвращаем пару: ID для проверок и адрес для открытия и сохранения.
    return vacancy_id, clean_link


def validate_delays(required=None, timeouts=()):
    """Проверяет паузы текущего этапа и указанные тайм-ауты."""
    # Без списка оставляем общую диагностику; явная группа изолирует этап.
    if required is None:
        required = tuple(name for name in vars(config) if name.startswith("DELAY_"))

    missing = [
        name for name in (*required, *timeouts) if not hasattr(config, name)
    ]
    if missing:
        raise ValueError("Не найдены настройки времени: " + ", ".join(missing))

    for name in timeouts:
        check_timeout(getattr(config, name), name)

    for name in required:
        settings = getattr(config, name)

        if not isinstance(settings, (tuple, list)) or len(settings) != 3:
            raise ValueError(f"{name}: нужны минимум, максимум и пояснение.")

        minimum, maximum, reason = settings
        # bool исключён: True и False не должны задавать длительность.
        if any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in (minimum, maximum)
        ):
            raise ValueError(f"{name}: границы должны быть конечными числами.")

        if not 0 <= minimum <= maximum:
            raise ValueError(f"{name}: требуется 0 <= минимум <= максимум.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{name}: нужно непустое текстовое пояснение.")


def create_stats(total):
    """Создаёт счётчики элементов подготовленной очереди."""
    return {"saved": 0, "skipped": 0, "errors": 0, "pending": total}


def print_summary(stats):
    """Печатает итог, в том числе при досрочной остановке."""
    if stats is None:
        print("\nИтог: очередь вакансий не подготовлена.")
        return

    print("\nИтог запуска:")
    if "sent" in stats:
        print(f"Новых откликов отправлено: {stats['sent']}")
    print(f"Сохранено: {stats['saved']}")
    print(f"Пропущено: {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Не обработано: {stats['pending']}")
