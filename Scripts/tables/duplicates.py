# duplicates.py

from core import utils


def build_id_index(rows):
    """Собирает номера строк для ID из колонки и ссылок."""
    # rows — пары (номер строки, данные), полученные из sheets.py.
    # В словаре ключом будет ID, а значением — множество номеров строк.
    id_rows = {}

    # Статус не фильтруем: строки с no и wait тоже резервируют ID.
    for row_number, row in rows:
        # Множество объединит одинаковый ID из колонки и ссылки этой строки.
        row_ids = {row["ID"].strip()}

        try:
            # Ссылка учитывается, даже если отдельная колонка ID пока пустая.
            # Второй результат — очищенная ссылка; здесь нужен только ID.
            vacancy_id, _ = utils.parse_vacancy_link(row["Ссылка"])
            row_ids.add(vacancy_id)
        except ValueError:
            # Пустая или неверная ссылка не прерывает построение индекса.
            # ID из отдельной колонки при этом остаётся в row_ids.
            pass

        for vacancy_id in row_ids:
            # Пустой ID не включаем в индекс.
            if vacancy_id:
                # setdefault создаёт множество для нового ID.
                # add запоминает строку; повтор в той же строке не дублируется.
                id_rows.setdefault(vacancy_id, set()).add(row_number)

    # Например, {"123": {2, 5}}: вакансия 123 встречается в строках 2 и 5.
    return id_rows


def inspect_link(row_number, row, id_rows):
    """Возвращает подготовленную ссылку или причину пропуска, не печатая её."""
    vacancy_id, clean_link = utils.parse_vacancy_link(row["Ссылка"])

    # Ручной ID не исправляем, если ссылка ведёт на другую вакансию.
    if row["ID"].strip() not in ("", vacancy_id):
        return None, "ID не совпадает со ссылкой."

    # Текущая строка не считается собственным дублем.
    duplicate_rows = id_rows.get(vacancy_id, set()) - {row_number}

    if duplicate_rows:
        numbers = ", ".join(
            str(number) for number in sorted(duplicate_rows)
        )
        return None, f"Дубликат в строках {numbers}."

    return {
        "id": vacancy_id,
        "link": clean_link,
    }, None


def prepare_link(row_number, row, id_rows):
    """Сохраняет прежний интерфейс обработчиков и вывод причины в консоль."""
    item, reason = inspect_link(row_number, row, id_rows)
    if reason:
        print(f"Строка {row_number}: {reason}")
    return item
