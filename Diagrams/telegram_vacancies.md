# Обработка вакансий Telegram

[Инструкция](../Docs/telegram.md) · [План, пункт 31](../PLAN.md)

```mermaid
flowchart TD
    Export["Вручную экспортировать один канал в JSON"] --> Check["Проверить наличие нужных постов и адрес канала"]
    Check --> Import["Сообщения из JSON: отдельный снимок каждого поста"]
    Import --> Files[("data/telegram: page.html и source.json")]
    Files --> VPN["Включить VPN вручную"]
    VPN --> Extract["Общий process-html: vacancy.json"]
    Extract --> Draft["Общий draft-html: письмо и анализ в draft.json"]
    Draft --> Review["Проверить содержание; выключить VPN"]
    Review --> Table["Общий import-results: новые строки отдельного листа"]
    Table --> Manual["Отправить отклик вручную"]
```

Получение сообщений из сети пока не реализовано. Посты не отправляются работодателям автоматически.
Формат JSON, паузы ИИ, проверка цитат и импорт партиями общие с сайтами компаний.
