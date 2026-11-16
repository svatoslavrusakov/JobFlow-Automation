"""Общее добавление новых строк: используется импортом hh и результатов сайтов."""

from core import config, stop_control, utils
from tables import duplicates, google_connection, sheets

IMPORT_BATCH_SIZE = 50


def import_rows(sheet, vacancies, headers=None, limit=None):
    """Добавляет партии без обновления существующих строк любого статуса."""
    request = google_connection.request_with_retry
    if headers is None:
        headers = request(sheets.read_headers, sheet)
    rows = request(sheets.read_vacancy_rows, sheet, fields=("ID", "Ссылка"), headers=headers)
    existing_ids = set(duplicates.build_id_index(rows))
    seen_ids = set(existing_ids)
    seen_links = {row["Ссылка"].strip() for _, row in rows if row["Ссылка"].strip()}
    pending = []
    for vacancy in vacancies:
        stop_control.check()
        key, link = str(vacancy["ID"]).strip(), vacancy["Ссылка"].strip()
        if key in seen_ids or link in seen_links:
            continue
        pending.append(vacancy)
        # Убираем повторы и внутри входных файлов; полный URL не очищаем.
        seen_ids.add(key)
        seen_links.add(link)
        if limit is not None and len(pending) >= limit:
            break

    added = 0
    for offset in range(0, len(pending), IMPORT_BATCH_SIZE):
        stop_control.check()
        if offset:
            utils.human_delay(config.DELAY_IMPORT_BATCH, cancelable=True)
        batch = pending[offset:offset + IMPORT_BATCH_SIZE]
        # Старая запись по заголовкам и RAW; кэш ID обновляется после ответа Google.
        sheets.save_vacancies(sheet, existing_ids, batch, headers=headers)
        added += len(batch)
    return added
