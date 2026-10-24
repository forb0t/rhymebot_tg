# Rhymes — Telegram-бот со случайными стихами

Бот присылает случайные стихотворения русских поэтов с сайта [russian-poetry.ru](https://russian-poetry.ru/) —
по кнопке в любой момент или по расписанию.

## Возможности

- 🎲 **Случайный стих** по кнопке: название, автор (ссылка на его страницу), текст с сохранёнными отступами,
  дата или место публикации. Под стихом — «🎲 Ещё стих» и «🏠 Меню»
- ⏰ **Рассылка**: каждый день, через день или раз в неделю, в выбранный час (08:00–22:00)
- Длинные стихи делятся по строфам на несколько сообщений
- Если бот был выключен, пропущенные рассылки не сыплются пачкой — приходит один стих, дальше по расписанию
- Если сайт со стихами не отвечает, бот повторяет запрос, а рассылку откладывает до восстановления

Всё управление — кнопками. Команда одна: `/start` (открывает меню). На любое сообщение в личке бот тоже показывает меню.

## Запуск

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # впишите токен от @BotFather
set -a; . ./.env; set +a
.venv/bin/python main.py
```

> ⚠️ Никогда не вписывайте токен в код и не коммитьте `.env` — токен из публичного репозитория
> украдут за минуты. Если токен утёк, отзовите его в @BotFather (*API Token → Revoke*).

### Как systemd-сервис пользователя

```ini
# ~/.config/systemd/user/rhymebot.service
[Service]
WorkingDirectory=%h/Applications/rhymebot
EnvironmentFile=%h/.config/rhymebot/env
Environment=RHYMES_DATA_DIR=%h/.local/share/rhymebot
ExecStart=%h/Applications/rhymebot/.venv/bin/python main.py
Restart=always
RestartSec=15
RestartPreventExitStatus=78

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now rhymebot
journalctl --user -u rhymebot -f
```

Без токена бот завершается с кодом 78, и systemd не перезапускает его впустую.

## Настройки

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Токен бота от @BotFather (обязательно) |
| `BOT_TIMEZONE` | `Europe/Moscow` | Часовой пояс рассылки |
| `RHYMES_DATA_DIR` | `.` | Где хранить базу подписок `rhymes.db` и лог `bot.log` |

Имя бота, описание и короткое описание заданы константами в начале `bot.py` и выставляются при каждом запуске.

## Структура проекта

```
├── main.py         # точка входа
├── bot.py          # Telegram-бот: меню, стихи, рассылка
├── poetry.py       # загрузка и разбор случайного стихотворения с russian-poetry.ru
├── storage.py      # SQLite: подписки на рассылку
└── bot_config.py   # настройки из окружения
```
