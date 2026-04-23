import html
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import db
from config import cfg, runtime
from texts import (
    EMP_CHECKLIST,
    EMP_KEYS,
    FLOW_BY_FIELD,
    FLOW_ORDER,
    HR_KEYS,
    HR_ROADMAP,
)

router = Router(name="hr")


class NewEmp(StatesGroup):
    name = State()


class Flow(StatesGroup):
    collecting = State()


def is_hr(tg_id: int) -> bool:
    return tg_id == cfg.hr_id


def esc(s) -> str:
    return html.escape(str(s or ""))


def progress_bar(done: int, total: int) -> str:
    filled = int(done / total * 10) if total else 0
    return "▓" * filled + "░" * (10 - filled)


def next_field(current: str) -> Optional[str]:
    try:
        i = FLOW_ORDER.index(current)
    except ValueError:
        return FLOW_ORDER[0]
    return FLOW_ORDER[i + 1] if i + 1 < len(FLOW_ORDER) else None


def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый сотрудник", callback_data="hr:new")],
            [InlineKeyboardButton(text="👥 Список сотрудников", callback_data="hr:list")],
        ]
    )


def list_kb(employees: list) -> InlineKeyboardMarkup:
    rows = []
    for e in employees:
        hr_checks = db.get_checks(e["token"], "hr")
        emp_checks = db.get_checks(e["token"], "emp")
        hr_done = sum(1 for k in HR_KEYS if hr_checks.get(k))
        emp_done = sum(1 for k in EMP_KEYS if emp_checks.get(k))
        status = "🟢" if e["telegram_id"] else "⚪"
        label = (
            f"{status} {e['name']} — HR {hr_done}/{len(HR_KEYS)} · "
            f"Сотр. {emp_done}/{len(EMP_KEYS)}"
        )
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"hr:emp:{e['token']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="hr:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def emp_card_kb(token: str, emp: dict) -> InlineKeyboardMarkup:
    hr_checks = db.get_checks(token, "hr")
    linked = bool(emp.get("telegram_id"))
    rows = []
    # Чек-лист дорожной карты HR (13 пунктов)
    for key, label in HR_ROADMAP:
        mark = "✅" if hr_checks.get(key) else "⬜"
        short = label if len(label) < 45 else label[:42] + "…"
        rows.append(
            [InlineKeyboardButton(text=f"{mark} {short}", callback_data=f"hr:t:{token}:{key}")]
        )

    # Кнопки повторной отправки интро и чек-листа (уже отправлялись автоматически)
    if linked:
        rows.append([
            InlineKeyboardButton(text="📩 Повторить интро", callback_data=f"hr:resend:{token}:intro"),
            InlineKeyboardButton(text="📋 Повторить чек-лист", callback_data=f"hr:resend:{token}:checklist"),
        ])

        # Ручная отправка материалов (каждая — запрос одного поля у HR)
        rows.append([
            InlineKeyboardButton(text="🔗 Отправить верификацию", callback_data=f"hr:send:{token}:verify"),
        ])
        rows.append([
            InlineKeyboardButton(text="✉️ Отправить доступ к почте", callback_data=f"hr:send:{token}:email"),
        ])
        rows.append([
            InlineKeyboardButton(text="📱 Отправить номер телефона", callback_data=f"hr:send:{token}:phone"),
        ])
        rows.append([
            InlineKeyboardButton(text="📝 Отправить NDA", callback_data=f"hr:send:{token}:nda"),
        ])
        rows.append([
            InlineKeyboardButton(text="💳 Отправить инвайт в кошелёк", callback_data=f"hr:send:{token}:wallet"),
        ])

        # Авто-цепочка: продолжить последовательную передачу, если ещё не завершена
        if emp["flow_step"] not in (None, "flow_done"):
            rows.append([
                InlineKeyboardButton(
                    text="▶️ Продолжить авто-цепочку",
                    callback_data=f"hr:flow:{token}",
                )
            ])

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"hr:emp:{token}"),
        InlineKeyboardButton(text="⬅️ К списку", callback_data="hr:list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_emp_card(emp: dict) -> str:
    hr_checks = db.get_checks(emp["token"], "hr")
    emp_checks = db.get_checks(emp["token"], "emp")
    hr_done = sum(1 for k in HR_KEYS if hr_checks.get(k))
    emp_done = sum(1 for k in EMP_KEYS if emp_checks.get(k))

    tg_line = (
        f"Telegram: <code>{emp['telegram_id']}</code>"
        if emp["telegram_id"]
        else "Telegram: <i>не привязан</i>"
    )
    wallet_line = (
        f"Кошелёк USDT (TRC20): <code>{esc(emp['tron_wallet'])}</code>"
        if emp.get("tron_wallet")
        else "Кошелёк: <i>ещё не получен</i>"
    )
    step = emp.get("flow_step") or "new"
    step_line = {
        "new": "Статус: <i>ссылка-приглашение не открыта</i>",
        "joined": "Статус: <b>присоединился, ждёт материалы</b>",
        "flow_done": "Статус: <b>все материалы отправлены ✅</b>",
    }.get(step, f"Статус: <b>ждём от HR — {FLOW_BY_FIELD[step]['ask']}</b>")

    emp_lines = []
    for key, label in EMP_CHECKLIST:
        mark = "✅" if emp_checks.get(key) else "⬜"
        emp_lines.append(f"{mark} {esc(label)}")

    invite_link = f"https://t.me/{cfg.emp_bot_username}?start={emp['token']}"

    return (
        f"<b>👤 {esc(emp['name'])}</b>\n"
        f"{tg_line}\n"
        f"{wallet_line}\n"
        f"{step_line}\n"
        f"Ссылка-приглашение: <code>{esc(invite_link)}</code>\n\n"
        f"<b>Прогресс HR:</b> {hr_done}/{len(HR_KEYS)} <code>{progress_bar(hr_done, len(HR_KEYS))}</code>\n"
        f"<b>Прогресс сотрудника:</b> {emp_done}/{len(EMP_KEYS)} <code>{progress_bar(emp_done, len(EMP_KEYS))}</code>\n\n"
        f"<b>Чек-лист сотрудника:</b>\n" + "\n".join(emp_lines) + "\n\n"
        f"<i>Нажимай на пункты дорожной карты ниже, чтобы отмечать свои шаги.</i>"
    )


async def ask_hr_for(token: str, field: str, state: FSMContext, chain: bool = True):
    """Запросить у HR значение для поля flow и выставить FSM.

    chain=True  — после отправки бот попросит следующее поле (авто-цепочка).
    chain=False — одиночная отправка: после успеха возврат в меню.
    """
    emp = db.get_by_token(token)
    if not emp:
        return
    spec = FLOW_BY_FIELD[field]
    if chain:
        db.set_step(token, field)
    await state.set_state(Flow.collecting)
    await state.update_data(token=token, field=field, chain=chain)
    hint = (
        "Команды: /skip — пропустить, /cancel — выйти."
        if chain
        else "Команда: /cancel — отменить."
    )
    await runtime.hr_bot.send_message(
        cfg.hr_id,
        f"⏳ Для сотрудника <b>{esc(emp['name'])}</b> пришли {spec['ask']}.\n\n"
        f"Отправь ссылку/текст одним сообщением. {hint}",
    )


async def kickoff_flow_from_emp_side(token: str):
    """
    Вызывается из emp_handlers после того, как сотрудник присоединился.
    Автоматически отправляет интро + чек-лист сотруднику, уведомляет HR,
    и предлагает начать передачу материалов.
    """
    emp = db.get_by_token(token)
    if not emp or not emp["telegram_id"]:
        return

    # 1. Интро (отправляется в emp-бот)
    from texts import INTRO_MESSAGE, CHECKLIST_INTRO
    from emp_handlers import emp_checklist_kb

    await runtime.emp_bot.send_message(emp["telegram_id"], INTRO_MESSAGE)
    db.set_check(token, "hr", "intro", True)

    # 2. Чек-лист (отправляется в emp-бот)
    await runtime.emp_bot.send_message(
        emp["telegram_id"], CHECKLIST_INTRO, reply_markup=emp_checklist_kb(token)
    )
    db.set_check(token, "hr", "checklist", True)

    # 3. HR-отбивка
    await runtime.hr_bot.send_message(
        cfg.hr_id,
        f"🎉 Сотрудник <b>{esc(emp['name'])}</b> присоединился к боту "
        f"(Telegram: <code>{emp['telegram_id']}</code>).\n\n"
        f"Ему уже отправлены:\n"
        f"✅ Интро-сообщение от Эммы\n"
        f"✅ Чек-лист онбординга\n\n"
        f"Сейчас попрошу у тебя материалы по очереди ⬇️",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="▶️ Начать передачу материалов",
                    callback_data=f"hr:flow:{token}",
                )
            ]],
        ),
    )


# ---------- Commands ----------


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if not is_hr(message.from_user.id):
        await message.answer(
            "Это HR-дашборд. Если ты новый сотрудник — открой ссылку, "
            f"которую прислал HR, на бота @{cfg.emp_bot_username}."
        )
        return
    await message.answer(
        f"Привет, {esc(cfg.hr_name)}! Это бот-дашборд для онбординга.",
        reply_markup=main_kb(),
    )


@router.message(Command("menu"))
async def menu(message: Message, state: FSMContext):
    if is_hr(message.from_user.id):
        await state.clear()
        await message.answer("Меню HR:", reply_markup=main_kb())


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    if is_hr(message.from_user.id):
        await state.clear()
        await message.answer("Ввод отменён.", reply_markup=main_kb())


@router.message(Command("skip"), Flow.collecting)
async def skip_field(message: Message, state: FSMContext):
    if not is_hr(message.from_user.id):
        return
    data = await state.get_data()
    token = data["token"]
    field = data["field"]
    emp = db.get_by_token(token)
    await message.answer(
        f"⏭ Шаг <i>{FLOW_BY_FIELD[field]['ask']}</i> пропущен для "
        f"<b>{esc(emp['name'])}</b>."
    )
    nxt = next_field(field)
    if nxt:
        await ask_hr_for(token, nxt, state)
    else:
        db.set_step(token, "flow_done")
        await state.clear()
        await message.answer(
            f"✅ Все шаги пройдены для <b>{esc(emp['name'])}</b>.",
            reply_markup=main_kb(),
        )


# ---------- Callbacks ----------


@router.callback_query(F.data == "hr:home")
async def cb_home(cb: CallbackQuery, state: FSMContext):
    if not is_hr(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text("Меню HR:", reply_markup=main_kb())
    await cb.answer()


@router.callback_query(F.data == "hr:list")
async def cb_list(cb: CallbackQuery):
    if not is_hr(cb.from_user.id):
        return
    employees = db.list_all()
    if not employees:
        await cb.message.edit_text(
            "Пока нет ни одного сотрудника. Создай первого.",
            reply_markup=main_kb(),
        )
    else:
        await cb.message.edit_text("Сотрудники:", reply_markup=list_kb(employees))
    await cb.answer()


@router.callback_query(F.data == "hr:new")
async def cb_new(cb: CallbackQuery, state: FSMContext):
    if not is_hr(cb.from_user.id):
        return
    await state.set_state(NewEmp.name)
    await cb.message.answer("Как зовут нового сотрудника? (Имя Фамилия)")
    await cb.answer()


@router.message(NewEmp.name)
async def new_name(message: Message, state: FSMContext):
    if not is_hr(message.from_user.id):
        return
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Попробуй ещё раз.")
        return
    token = db.create_employee(name)
    await state.clear()
    link = f"https://t.me/{cfg.emp_bot_username}?start={token}"
    await message.answer(
        f"✅ Создан: <b>{esc(name)}</b>\n\n"
        f"Отправь сотруднику эту ссылку (через неё он подключится к "
        f"@{cfg.emp_bot_username}):\n<code>{esc(link)}</code>",
        reply_markup=main_kb(),
    )


@router.callback_query(F.data.startswith("hr:emp:"))
async def cb_emp(cb: CallbackQuery):
    if not is_hr(cb.from_user.id):
        return
    token = cb.data.split(":", 2)[2]
    emp = db.get_by_token(token)
    if not emp:
        await cb.answer("Сотрудник не найден", show_alert=True)
        return
    await cb.message.edit_text(render_emp_card(emp), reply_markup=emp_card_kb(token, emp))
    await cb.answer()


@router.callback_query(F.data.startswith("hr:t:"))
async def cb_toggle(cb: CallbackQuery):
    if not is_hr(cb.from_user.id):
        return
    _, _, token, key = cb.data.split(":", 3)
    db.toggle_check(token, "hr", key)
    emp = db.get_by_token(token)
    await cb.message.edit_text(render_emp_card(emp), reply_markup=emp_card_kb(token, emp))
    await cb.answer("Готово")


@router.callback_query(F.data.startswith("hr:flow:"))
async def cb_flow(cb: CallbackQuery, state: FSMContext):
    if not is_hr(cb.from_user.id):
        return
    token = cb.data.split(":", 2)[2]
    emp = db.get_by_token(token)
    if not emp or not emp["telegram_id"]:
        await cb.answer("Сотрудник ещё не присоединился", show_alert=True)
        return
    field = emp["flow_step"]
    if field in (None, "new", "joined", "flow_done"):
        field = FLOW_ORDER[0]
    await ask_hr_for(token, field, state, chain=True)
    await cb.answer()


@router.callback_query(F.data.startswith("hr:send:"))
async def cb_send_single(cb: CallbackQuery, state: FSMContext):
    if not is_hr(cb.from_user.id):
        return
    _, _, token, field = cb.data.split(":", 3)
    emp = db.get_by_token(token)
    if not emp or not emp["telegram_id"]:
        await cb.answer("Сотрудник ещё не присоединился", show_alert=True)
        return
    if field not in FLOW_BY_FIELD:
        await cb.answer("Неизвестное поле", show_alert=True)
        return
    await ask_hr_for(token, field, state, chain=False)
    await cb.answer()


@router.callback_query(F.data.startswith("hr:resend:"))
async def cb_resend(cb: CallbackQuery):
    """Повторная отправка интро или чек-листа (без запроса HR — просто шлём заново)."""
    if not is_hr(cb.from_user.id):
        return
    _, _, token, kind = cb.data.split(":", 3)
    emp = db.get_by_token(token)
    if not emp or not emp["telegram_id"]:
        await cb.answer("Сотрудник ещё не присоединился", show_alert=True)
        return
    from texts import INTRO_MESSAGE, CHECKLIST_INTRO
    from emp_handlers import emp_checklist_kb

    if kind == "intro":
        await runtime.emp_bot.send_message(emp["telegram_id"], INTRO_MESSAGE)
        db.set_check(token, "hr", "intro", True)
        await cb.answer("Интро отправлено повторно")
    elif kind == "checklist":
        await runtime.emp_bot.send_message(
            emp["telegram_id"], CHECKLIST_INTRO, reply_markup=emp_checklist_kb(token)
        )
        db.set_check(token, "hr", "checklist", True)
        await cb.answer("Чек-лист отправлен повторно")
    else:
        await cb.answer("Неизвестный тип", show_alert=True)
        return
    emp = db.get_by_token(token)
    await cb.message.edit_text(render_emp_card(emp), reply_markup=emp_card_kb(token, emp))


# ---------- Flow text input ----------


@router.message(Flow.collecting)
async def flow_input(message: Message, state: FSMContext):
    if not is_hr(message.from_user.id):
        return
    data = await state.get_data()
    token = data["token"]
    field = data["field"]
    chain = data.get("chain", True)
    emp = db.get_by_token(token)
    if not emp or not emp["telegram_id"]:
        await state.clear()
        await message.answer("Сотрудник не найден или не привязан.")
        return

    spec = FLOW_BY_FIELD[field]
    body = message.text or ""

    # Отправляем сотруднику
    parts = [spec["header"], "", esc(body)]
    if spec.get("extra"):
        parts += ["", spec["extra"]]
    await runtime.emp_bot.send_message(emp["telegram_id"], "\n".join(parts))

    # Отмечаем в HR-чек-листе
    db.set_check(token, "hr", field, True)

    await message.answer(
        f"✅ Отправлено сотруднику <b>{esc(emp['name'])}</b>: {spec['ask']}"
    )

    if chain:
        nxt = next_field(field)
        if nxt:
            await ask_hr_for(token, nxt, state, chain=True)
        else:
            db.set_step(token, "flow_done")
            await state.clear()
            await message.answer(
                f"🎉 Все материалы отправлены <b>{esc(emp['name'])}</b>.\n"
                f"Теперь подожди, пока сотрудник пройдёт свой чек-лист. "
                f"Не забудь остальные пункты дорожной карты.",
                reply_markup=main_kb(),
            )
    else:
        # Одиночная отправка — возвращаем HR на карточку сотрудника
        await state.clear()
        emp_fresh = db.get_by_token(token)
        await message.answer(
            render_emp_card(emp_fresh),
            reply_markup=emp_card_kb(token, emp_fresh),
        )


# ---------- Fallback ----------


@router.message()
async def fallback(message: Message):
    if is_hr(message.from_user.id):
        await message.answer("Используй /menu.", reply_markup=main_kb())
    else:
        await message.answer(
            "Это HR-дашборд. Если ты новый сотрудник — открой ссылку, "
            f"которую прислал HR, на бота @{cfg.emp_bot_username}."
        )
