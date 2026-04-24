import html

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
import notion_sync
from config import cfg, runtime
from texts import EMP_CHECKLIST, EMP_KEYS

router = Router(name="emp")


class WalletInput(StatesGroup):
    waiting = State()


class SelfRegister(StatesGroup):
    awaiting_name = State()


SELF_REGISTER_PROMPT = (
    "Привет, это HR-бот SquareFi.\n\n"
    "Если тебя пригласили — открой ссылку-приглашение от HR. "
    "Если хочешь начать онбординг самостоятельно — напиши, пожалуйста, свои "
    "ФИО на английском (как в паспорте)."
)

PENDING_APPROVAL_TEXT = (
    "✅ Я передала твой запрос HR. Жду, пока подтвердят — "
    "как только это произойдёт, я сразу пришлю следующий шаг. "
    "Обычно это занимает до пары часов."
)

REJECT_TEXT = (
    "К сожалению, твой запрос на онбординг не подтверждён. "
    "Если это ошибка — свяжись с HR напрямую."
)


def esc(s) -> str:
    return html.escape(str(s or ""))


def progress_bar(done: int, total: int) -> str:
    filled = int(done / total * 10) if total else 0
    return "▓" * filled + "░" * (10 - filled)


def emp_checklist_kb(token: str) -> InlineKeyboardMarkup:
    checks = db.get_checks(token, "emp")
    rows = []
    for key, label in EMP_CHECKLIST:
        mark = "✅" if checks.get(key) else "⬜"
        rows.append(
            [InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"emp:t:{key}")]
        )
    rows.append(
        [InlineKeyboardButton(text="💳 Отправить адрес кошелька", callback_data="emp:wallet")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_emp(emp: dict) -> str:
    checks = db.get_checks(emp["token"], "emp")
    done = sum(1 for k in EMP_KEYS if checks.get(k))
    return (
        f"<b>Твой онбординг-чек-лист</b>\n"
        f"Прогресс: {done}/{len(EMP_KEYS)} <code>{progress_bar(done, len(EMP_KEYS))}</code>\n\n"
        f"Отмечай пункты, как только выполнишь. HR видит твой прогресс."
    )


# ---------- Commands ----------


@router.message(CommandStart(deep_link=True))
async def start_deep(message: Message, command):
    from hr_handlers import kickoff_flow_from_emp_side

    token = (command.args or "").strip()
    emp = db.get_by_token(token)
    if not emp:
        await message.answer("Ссылка-приглашение недействительна. Свяжись с HR.")
        return
    if emp["telegram_id"] and emp["telegram_id"] != message.from_user.id:
        await message.answer("Эта ссылка уже использована другим пользователем.")
        return
    fresh_join = not emp["telegram_id"]
    if fresh_join:
        db.link_employee(token, message.from_user.id)
        # Пишем Telegram ID в Notion
        emp_after = db.get_by_token(token)
        if emp_after.get("notion_page_id"):
            await notion_sync.set_telegram_id(
                emp_after["notion_page_id"], message.from_user.id
            )

    # Сразу запускаем авто-flow: интро + чек-лист + отбивка HR + запрос материалов
    if fresh_join:
        await kickoff_flow_from_emp_side(token)
    else:
        # Повторный /start — просто покажем чек-лист
        emp = db.get_by_token(token)
        await message.answer(render_emp(emp), reply_markup=emp_checklist_kb(token))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    emp = db.get_by_tg(message.from_user.id)
    if emp:
        if emp.get("flow_step") == "pending_approval":
            await message.answer(PENDING_APPROVAL_TEXT)
        else:
            await message.answer(
                render_emp(emp), reply_markup=emp_checklist_kb(emp["token"])
            )
        return
    # Новый пользователь — предлагаем self-register
    await state.set_state(SelfRegister.awaiting_name)
    await message.answer(SELF_REGISTER_PROMPT)


@router.message(SelfRegister.awaiting_name)
async def self_register_name(message: Message, state: FSMContext):
    from hr_handlers import self_register_kb

    name = (message.text or "").strip()
    if len(name) < 3 or " " not in name:
        await message.answer(
            "Пожалуйста, напиши ФИО полностью (имя и фамилию) латиницей."
        )
        return
    # На случай гонки — проверяем, не создан ли уже
    existing = db.get_by_tg(message.from_user.id)
    if existing:
        await state.clear()
        if existing.get("flow_step") == "pending_approval":
            await message.answer(PENDING_APPROVAL_TEXT)
        else:
            await message.answer(
                render_emp(existing),
                reply_markup=emp_checklist_kb(existing["token"]),
            )
        return

    token = db.create_employee_self(name, message.from_user.id)
    await state.clear()
    username = (
        f"@{message.from_user.username}" if message.from_user.username else "—"
    )
    await runtime.hr_bot.send_message(
        cfg.hr_id,
        f"🆕 <b>Новый запрос на онбординг</b>\n\n"
        f"ФИО: <b>{esc(name)}</b>\n"
        f"Telegram: <code>{message.from_user.id}</code> · {esc(username)}\n\n"
        f"Подтверди, чтобы начать процесс.",
        reply_markup=self_register_kb(token),
    )
    await message.answer(PENDING_APPROVAL_TEXT)


@router.message(Command("getme"))
async def getme(message: Message):
    uid = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    name = message.from_user.full_name
    await message.answer(
        f"Твои данные для HR (перешли это сообщение):\n\n"
        f"ID: <code>{uid}</code>\n"
        f"Имя: {esc(name)}\n"
        f"Username: {esc(username)}"
    )


@router.message(Command("checklist"))
async def checklist(message: Message):
    emp = db.get_by_tg(message.from_user.id)
    if emp:
        await message.answer(render_emp(emp), reply_markup=emp_checklist_kb(emp["token"]))


# ---------- Callbacks ----------


@router.callback_query(F.data.startswith("emp:t:"))
async def cb_toggle(cb: CallbackQuery):
    emp = db.get_by_tg(cb.from_user.id)
    if not emp:
        await cb.answer()
        return
    key = cb.data.split(":", 2)[2]
    if key not in EMP_KEYS:
        await cb.answer()
        return
    data = db.toggle_check(emp["token"], "emp", key)
    label = dict(EMP_CHECKLIST)[key]
    status = "✅ отметил" if data.get(key) else "⬜ снял отметку"
    await cb.message.edit_reply_markup(reply_markup=emp_checklist_kb(emp["token"]))
    await cb.answer("Сохранено")
    # Синк в Notion
    await notion_sync.sync_emp_check(emp.get("notion_page_id"), key, bool(data.get(key)))
    await runtime.hr_bot.send_message(
        cfg.hr_id,
        f"📬 <b>{esc(emp['name'])}</b> {status}: <i>{esc(label)}</i>",
    )


@router.callback_query(F.data == "emp:wallet")
async def cb_wallet(cb: CallbackQuery, state: FSMContext):
    emp = db.get_by_tg(cb.from_user.id)
    if not emp:
        await cb.answer()
        return
    await state.set_state(WalletInput.waiting)
    await cb.message.answer("Пришли адрес кошелька USDT (TRC20) — я передам HR.")
    await cb.answer()


@router.message(WalletInput.waiting)
async def wallet_input(message: Message, state: FSMContext):
    emp = db.get_by_tg(message.from_user.id)
    if not emp:
        await state.clear()
        return
    wallet = message.text.strip()
    db.set_wallet(emp["token"], wallet)
    await state.clear()
    await message.answer("✅ Спасибо! Адрес сохранён и передан HR.")
    # Синк в Notion: адрес кошелька
    if emp.get("notion_page_id"):
        await notion_sync.set_wallet(emp["notion_page_id"], wallet)
    await runtime.hr_bot.send_message(
        cfg.hr_id,
        f"💳 <b>{esc(emp['name'])}</b> прислал адрес кошелька:\n<code>{esc(wallet)}</code>",
    )


@router.message()
async def fallback(message: Message, state: FSMContext):
    emp = db.get_by_tg(message.from_user.id)
    if emp:
        if emp.get("flow_step") == "pending_approval":
            await message.answer(PENDING_APPROVAL_TEXT)
        else:
            await message.answer(
                render_emp(emp), reply_markup=emp_checklist_kb(emp["token"])
            )
        return
    # Новый пользователь написал произвольное сообщение — переводим в self-register
    await state.set_state(SelfRegister.awaiting_name)
    await message.answer(SELF_REGISTER_PROMPT)
