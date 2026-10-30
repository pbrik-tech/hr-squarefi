# HR SquareFi — онбординг-бот

Вся рабочая информация о проекте. Обновляй этот файл, когда меняется что-то важное
(деплой, интеграции, процесс, договорённости).

## Что это

Два Telegram-бота в одном процессе с общей SQLite-базой — онбординг новых сотрудников SquareFi / Mosta.

| Бот | Для кого | Роль |
|---|---|---|
| `@squarefiteamboardbot` | HR (только Полина, `HR_ID`) | Дашборд: сотрудники, карточки, отправка материалов, оффер, Fleet |
| `@emmahrsquarefibot` | Новые сотрудники | Ассистент «Эмма»: регистрация, чек-лист, материалы, кошелёк, чат с HR |

- Репозиторий: https://github.com/pbrik-tech/hr-squarefi (ветка `main`, коммиты прямо в `main`)
- Локально: `/Users/polinabrik/Desktop/AI/Work/HR bot/hr-squarefi`
- Владелец / HR-контакт в текстах: `@polina_brik`

## Стек и деплой

- Python 3.11 (`runtime.txt`), aiogram 3.13, aiohttp, python-dotenv
- Хостинг: **Railway**, builder Nixpacks, старт `python main.py` (`railway.json`, `Procfile` → `worker`)
- Деплой: пуш в `main` → Railway пересобирает (проверять во вкладке Deployments)
- БД: SQLite-файл на Railway Volume, путь из `DB_PATH` (по умолчанию `bot.db`). Один инстанс — масштабировать нельзя
- Railway CLI установлен (`/opt/homebrew/bin/railway`), но нужен `railway login` + `railway link`

## Переменные окружения

| Переменная | Обязательна | Назначение |
|---|---|---|
| `HR_BOT_TOKEN`, `HR_BOT_USERNAME` | да | HR-бот |
| `EMP_BOT_TOKEN`, `EMP_BOT_USERNAME` | да | Бот сотрудника |
| `HR_ID` | да | Telegram ID HR — только ему доступен HR-бот |
| `HR_NAME` | нет | Имя HR в приветствии |
| `NOTION_TOKEN`, `NOTION_DB_ID` | нет | Синк в Notion; без них синк молча выключен |
| `DB_PATH` | нет | Путь к SQLite (на Railway — на Volume) |

`.env` и `bot.db` в `.gitignore`, секреты в git не коммитить.

## Структура кода

- `main.py` — поднимает оба бота (`asyncio.gather`, polling), FSM в `SQLiteStorage`
- `config.py` — `cfg` (env) и `runtime` (ссылки на оба `Bot`, чтобы боты писали друг другу)
- `db.py` — таблицы `employees`, `audit_log`, `messages_log`; шаг сотрудника в `employees.flow_step`
  (`new | pending_approval | joined | verify | email | phone | nda | wallet | flow_done`)
- `storage.py` — FSM-хранилище aiogram в SQLite (переживает рестарты)
- `hr_handlers.py` — HR-бот: меню, список, карточка, оффер, отправка материалов, approve/reject, прокси-чат, Fleet
- `emp_handlers.py` — бот сотрудника: deep-link `/start <token>`, саморегистрация, чек-лист, кошелёк, фото, чат с HR
- `texts.py` — **все тексты** и списки шагов (`HR_ROADMAP`, `EMP_CHECKLIST`, `FLOW`, `ACCESS_FLOW`). Тексты держать здесь, не в хендлерах
- `notion_sync.py` — синк в базу Notion **HR / Team** (с 10.2026 вместо HR / Employments)
- `tests/` — pytest (`conftest.py` даёт фикстуру `tmp_db`)
- `AUDIT.md` — аудит от 2026-04-24 (часть пунктов уже закрыта, см. историю коммитов)

## Сценарий онбординга

1. HR создаёт сотрудника → ссылка `https://t.me/emmahrsquarefibot?start=<token>`; либо сотрудник сам пишет боту, вводит имя латиницей, HR подтверждает (approve/reject)
2. Бот шлёт интро Эммы и чек-лист
3. HR по кнопкам отправляет материалы цепочкой `FLOW`: верификация → почта (+2FA) → номер → NDA → кошелёк
4. Доступы `ACCESS_FLOW`: Slack (фиксированный текст — инвайт уходит на рабочую почту, у HR ничего не спрашивается), CRM, Notion, Админ-панель
5. Сотрудник присылает адрес USDT (TRC20), отмечает пункты — HR получает уведомления, данные уходят в Notion
6. Фото для «Команды», welcome-сообщение, в конце агент **Fleet** (SOC 2) — когда выданы почта, Slack и Notion
7. Карточка сотрудника в HR-боте: одна кнопка на шаг `HR_ROADMAP`. Шаги из `ROADMAP_ACTIONS` (`hr_handlers.py`) по нажатию отправляются сотруднику, остальные — просто галочка. Чек-лист сотрудника и редкие действия (авто-цепочка, черновик для #general, журнал) — в подменю «👤 Чек-лист сотрудника» и «⋯ Ещё»
8. `/stale` — зависшие онбординги, `/wipe` — очистка базы (с подтверждением)

Чек-лист сотрудника (8): верификация, вход в почту, 2FA, NDA, договор (если нужен), рабочий номер, кошелёк, Fleet.
Дорожная карта HR (`HR_ROADMAP`): первый шаг — оффер.

## Notion

Колонки базы HR / Team, в которые пишет бот — см. `EMP_NOTION_MAP`, `HR_NOTION_MAP` и константы `*_COLUMN` в `notion_sync.py`
(SumSub, NDA, Agreement, Email access, Wallet issued, Fleet MDM, VIP, Slack/CRM/Notion access, Wallet, Telegram ID, Phone, Photo, Status = On Probation).
Для `email_2fa`, `phone` (галочка) и `admin_access` колонок нет.

## Разработка

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

- Перед пушем гонять тесты
- Тексты бота — от лица Эммы, на «ты», коротко, абзацами через пустую строку, HTML-разметка Telegram
- После пуша проверить, что деплой в Railway прошёл, и пройти сценарий тестовым аккаунтом

## История изменений (ключевое)

- 2026-10-30 — карточка сотрудника сокращена с ~44 рядов кнопок до 23: убраны дубли «галочка + кнопка отправки», подменю для чек-листа сотрудника и редких действий; канал представления — #general
- 2026-10-30 — `f15a2f4`: новые тексты Эммы (короче и дружелюбнее), строки из `emp_handlers.py` вынесены в `texts.py`, Slack-шаг отправляет готовый текст без ввода HR, тесты на карточку и Slack
- `286821d` — фикс KeyError `flow_done` в карточке сотрудника
- `e9aec32` — синк в Notion HR / Team, Fleet как финальный шаг
