# Карта проекта

[Краткий запуск](../README.md) · [План разработки](../PLAN.md)

## Где находится код

В корне `Scripts/` находятся три файла запуска. Модули распределены по назначению:

```text
Scripts/
├── run.py              # запуск выбранного этапа
├── gui.py              # запуск интерфейса
├── save_search_html.py # сохранение открытого поиска hh
├── core/               # настройки, параметры, паузы, остановка и отбор строк
├── tables/             # Google Таблицы: колонки, строки и запись результатов
├── hh/                 # браузер, поиск, чтение вакансий и отправка откликов
├── telegram/           # чтение локального JSON-экспорта канала
├── html_tools/         # разбор HTML и хранение снимков
├── workflows/          # последовательности обработки
├── ai/                 # запросы к ИИ, проверка JSON и экспорт резюме
├── ui/                 # окна, вкладки, редакторы и фоновые задачи
└── desktop/            # экранный режим и калибровка
```

`Scripts/Prototype/` хранит прежний прототип и не участвует в запуске программы.
Локальные данные, ключи и настройки остаются в `data/` в корне проекта.
Корень определяется один раз в `core/settings_defaults.py`; перенос модулей не меняет пути к данным.

## Как читать основные сценарии

`run.py` загружает только выбранный обработчик. Старые команды `run.py`, `gui.py` и
`save_search_html.py` сохранены. Для отдельных этапов используйте `run.py` с режимом из
[списка команд](stages.md).

| Сценарий | Последовательность модулей |
|---|---|
| Живой поиск | `workflows/search.py` → `hh/hh_search.py` → `hh/vacancy_processor.py` → `tables/sheets.py` |
| Заполнение по ссылкам | `workflows/fill.py` → `hh/vacancy_processor.py` → `hh/vacancy_reader.py` → `tables/sheets.py` |
| Импорт HTML | `workflows/import_hh_links.py` → `html_tools/hh_search_html.py` → `tables/sheets.py` |
| Сохранение страниц поиска | `workflows/save_search_html.py` → `hh/hh_search.py` |
| Сообщения Telegram | `workflows/import_telegram.py` → `telegram/export.py` → `html_tools/html_storage.py`; затем общие этапы HTML |
| Снимки внешних вакансий | `workflows/collect_html.py` → `html_tools/html_storage.py` |
| Распознавание снимков | `workflows/process_html.py` → `ai/html_vacancy.py` → `core/vacancy.py` |
| Импорт готовых результатов | `workflows/import_results.py` → `ai/sheet.py` (поля) → `tables/import_rows.py` → `tables/sheets.py` |
| Локальные письма компаний | `workflows/process_html.py` → `ai/html_draft.py` → общий `ai/draft.py` |
| Письма через ИИ | `ai/process_ai.py` → `ai/draft.py` → `ai/gateway.py` → `ai/sheet.py` |
| Ключевые слова | `workflows/keywords.py` → `ai/requirements.py` → `tables/sheets.py` |
| Отправка | `workflows/send_applications.py` → `hh/application_sender.py` → `tables/application_sheet.py` |
| Проверка ответов | `workflows/check_responses.py` → `hh/response_reader.py` → `tables/response_sheet.py` |

## Общие части

- `core/settings_store.py`, `core/settings_defaults.py`, `core/config.py` — чтение и сохранение настроек.
- `core/row_queue.py`, `core/run_options.py` — общие правила отбора и параметры одного запуска.
- `core/vacancy.py` — единые поля и проверка вакансий hh и внешних сайтов.
- `ai/pacing.py` — одна пауза перед следующей попыткой ИИ для писем, ключевых слов и HTML.
- `tables/import_rows.py` — общий импорт партиями для HTML hh и готовых результатов компаний.
- `core/stop_control.py`, `core/sound_alarm.py` — остановка и звуковой сигнал.
- `tables/google_connection.py` — подключение и ограниченный повтор явного отказа 429.
- `tables/table_columns.py`, `tables/column_catalog.py` — назначение колонок и справка.
- `tables/duplicates.py` — проверка ID; `tables/queue_preview.py` — снимок очереди для окна.
- `tables/letter_review.py` — ручное одобрение письма; `ai/resume_docx.py` — экспорт черновика.
- `ui/app.py`, `ui/runner.py`, `ui/jobs.py` — главное окно, дочерний процесс и фоновые действия.
- `ui/queue.py`, `ui/letter.py`, `ui/resume.py` — очередь, редактор письма и панель резюме.
- `ui/settings.py`, `ui/delays.py`, `ui/columns.py`, `ui/desktop.py` — отдельные панели.
- `ui/workflow.py` — общая панель запуска и журнала для hh, компаний и Telegram.
- `ui/scroll.py`, `ui/options.py` — прокрутка и поля отбора строк.

Данные передаются словарями с названиями колонок. Обработчики сохраняют номера строк и
перед изменением проверяют исходные значения. HTML-импорт записывает партии по снимку шапки.
Оставшиеся работы и история решений находятся в [PLAN.md](../PLAN.md).
