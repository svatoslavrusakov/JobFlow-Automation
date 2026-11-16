# vacancy_processor.py

from gspread.exceptions import APIError
from requests.exceptions import RequestException
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from urllib3.exceptions import HTTPError

from core import config
from tables import sheets
from core import utils
from hh import vacancy_reader


def process_vacancy(
    driver,
    sheet,
    item,
    stats,
    existing_ids=None,
    row_number=None,
    original_link=None,
):
    """Обрабатывает вакансию. True — продолжать, False — остановить запуск."""
    if row_number is None and existing_ids is None:
        raise ValueError("Для добавления вакансии нужен набор existing_ids.")
    if row_number is not None and original_link is None:
        raise ValueError("Для дополнения строки нужна исходная ссылка.")

    vacancy_id = item["id"]

    try:
        vacancy = vacancy_reader.read_vacancy(driver, item)
    except PermissionError as error:
        # Потеря авторизации касается всей очереди, а не одной вакансии.
        print(f"Запуск остановлен: {error}")
        stats["errors"] += 1
        stats["pending"] -= 1
        return False
    except (NoSuchElementException, StaleElementReferenceException, ValueError) as error:
        # Ожидаемая ошибка страницы: очередь можно продолжить после паузы.
        print(f"Не удалось прочитать вакансию {vacancy_id}: {error}")
        stats["errors"] += 1
        stats["pending"] -= 1
        utils.human_delay(config.DELAY_BETWEEN_VACANCIES, cancelable=True)
        return True
    except (WebDriverException, HTTPError) as error:
        # Эти исключения включают потерю сессии и разрыв связи с драйвером.
        print(f"Ошибка работы с браузером: {error}")
        print("Запуск остановлен. Проверьте Chrome.")
        stats["errors"] += 1
        stats["pending"] -= 1
        return False
    except Exception:
        # Ошибку программы показываем с диагностикой, а не пропускаем.
        stats["errors"] += 1
        stats["pending"] -= 1
        raise

    vacancy["Статус"] = "new"

    if not save_result(sheet, vacancy, stats, existing_ids, row_number, original_link):
        return False

    utils.human_delay(config.DELAY_BETWEEN_VACANCIES, cancelable=True)
    return True


def save_result(sheet, vacancy, stats, existing_ids=None, row_number=None, original_link=None):
    """Сохраняет данные и счётчики; True — продолжать очередь, False — остановить."""
    vacancy_id = vacancy["ID"]
    try:
        if row_number is None:
            # Кэш ID меняется внутри save_vacancy только после успешной записи.
            sheets.save_vacancy(sheet, existing_ids, vacancy)
        else:
            sheets.fill_vacancy_row(
                sheet, row_number, original_link, vacancy,
            )
            print(f"Строка {row_number}: данные сохранены.")
    except KeyboardInterrupt:
        # Google мог принять запись до прерывания; результат пока неизвестен.
        print("Сохранение прервано. Проверьте результат в таблице перед повторным запуском.")
        raise
    except (ValueError, APIError, RequestException, HTTPError, WebDriverException, OSError) as error:
        stats["errors"] += 1
        stats["pending"] -= 1
        if row_number is None:
            print(f"Ошибка сохранения вакансии {vacancy_id}: {error}")
            print("Проверьте наличие строки в таблице перед повторным запуском.")
            return False

        if isinstance(error, (WebDriverException, HTTPError)):
            print(f"Ошибка работы с браузером: {error}")
            print("Запуск остановлен. Проверьте Chrome.")
            return False

        # Ошибка дополнения строки сохраняет возможность повторной попытки.
        print(f"Строка {row_number}: ошибка — {error}")
        if isinstance(error, (APIError, RequestException, OSError)):
            print("Проверьте результат записи в таблице.")
    except Exception:
        stats["errors"] += 1
        stats["pending"] -= 1
        raise
    else:
        # Считаем успех до паузы: Ctrl+C после записи не должен его потерять.
        stats["saved"] += 1
        stats["pending"] -= 1

    return True
