# Onboarding Bot (2 bots, shared DB)

Два Telegram-бота с общей SQLite-базой:

- **`@squarefiteamboardbot`** — HR-дашборд (только для Полины)
- **`@emmahrsquarefibot`** — бот для новых сотрудников

Оба бота запускаются из одного процесса `main.py` и общаются через общий `bot.db` + shared runtime references.

## Архитектура

```
HR пишет в @squarefiteamboardbot   ──┐
                                    ├──▶  main.py (asyncio.gather)
Сотрудник пишет в @emmahrsquarefibot ┘         │
                                               ▼
                                         bot.db (SQLite)

Когда HR жмёт "Отправить интро" → hr_handlers.py вызывает runtime.emp_bot.send_message(emp_tg_id, ...)
Когда сотрудник ставит галочку → emp_handlers.py вызывает runtime.hr_bot.send_message(HR_ID, ...)
```

## Файлы

- `main.py` — поднимает оба бота в одном процессе
- `config.py` — загрузка `.env` + runtime-сингелтон (ссылки на оба `Bot()`)
- `db.py` — SQLite (таблица `employees`)
- `hr_handlers.py` — хендлеры HR-бота (меню, список, карточка сотрудника, отправка материалов)
- `emp_handlers.py` — хендлеры бота для сотрудников (чек-лист, адрес кошелька)
- `texts.py` — тексты сообщений + списки HR/emp чек-листов
- `.env` — токены + ID (не в git)

## Запуск

```bash
cd onboarding-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Заполни: HR_BOT_TOKEN, HR_BOT_USERNAME, EMP_BOT_TOKEN, EMP_BOT_USERNAME, HR_ID, HR_NAME

python main.py
```

## Сценарий

1. HR пишет `/start` в `@squarefiteamboardbot` → видит меню («➕ Новый сотрудник», «👥 Список»)
2. Создаёт сотрудника → получает ссылку `https://t.me/emmahrsquarefibot?start=<token>`
3. Отправляет ссылку сотруднику
4. Сотрудник переходит → бот для сотрудников привязывает его и уведомляет HR в HR-боте
5. HR открывает карточку сотрудника → жмёт «📩 Интро», «📋 Чек-лист», «🔗 Верификация», «✉️ Почта», «💳 Инвайт в кошелек» — бот для сотрудников доставляет сообщения
6. Сотрудник отмечает галочки в чек-листе → HR получает уведомления в HR-боте

## Чек-листы

HR (13 шагов, `texts.py::HR_ROADMAP`): оффер, интро, чек-лист, верификация, почта, кошелёк, тариф, Slack/CRM/Notion, командные чаты, Slack-анонс, ежедневный звонок, Notion Team, ДР в календарь.

Сотрудник (6 пунктов, `texts.py::EMP_CHECKLIST`): верификация, NDA, договор, почта+2FA, телефон, кошелёк.
