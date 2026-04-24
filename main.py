import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
import emp_handlers
import hr_handlers
from config import cfg, runtime
from storage import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("onboarding")


async def main():
    db.init_db()

    default = DefaultBotProperties(parse_mode=ParseMode.HTML)
    hr_bot = Bot(token=cfg.hr_bot_token, default=default)
    emp_bot = Bot(token=cfg.emp_bot_token, default=default)

    runtime.hr_bot = hr_bot
    runtime.emp_bot = emp_bot

    hr_dp = Dispatcher(storage=SQLiteStorage())
    emp_dp = Dispatcher(storage=SQLiteStorage())
    hr_dp.include_router(hr_handlers.router)
    emp_dp.include_router(emp_handlers.router)

    await hr_bot.delete_webhook(drop_pending_updates=True)
    await emp_bot.delete_webhook(drop_pending_updates=True)

    log.info(
        "Starting bots: HR=@%s (chat_id=%s), EMP=@%s",
        cfg.hr_bot_username,
        cfg.hr_id,
        cfg.emp_bot_username,
    )

    await asyncio.gather(
        hr_dp.start_polling(hr_bot),
        emp_dp.start_polling(emp_bot),
    )


if __name__ == "__main__":
    asyncio.run(main())
