import os
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    hr_bot_token: str = os.environ["HR_BOT_TOKEN"]
    hr_bot_username: str = os.environ["HR_BOT_USERNAME"]
    emp_bot_token: str = os.environ["EMP_BOT_TOKEN"]
    emp_bot_username: str = os.environ["EMP_BOT_USERNAME"]
    hr_id: int = int(os.environ["HR_ID"])
    hr_name: str = os.environ.get("HR_NAME", "HR")


class Runtime:
    """Shared references between the two bots — set once at startup."""
    hr_bot: Optional[Bot] = None
    emp_bot: Optional[Bot] = None


cfg = Config()
runtime = Runtime()
