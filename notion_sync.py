import logging
import os
import re
from typing import Optional

import aiohttp

log = logging.getLogger("notion")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")
NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"

# Соответствие внутренних ключей чек-листа → названия колонок в Notion.
# ВАЖНО: колонка "Personа" содержит кириллическую «а» (U+0430).
EMP_NOTION_MAP = {
    "verification": "Personа",
    "nda": "NDA",
    "contract": "Agreement",
    "gmail_access": "Email",  # галочка Email в Notion ставится когда доступ к почте выдан
    "wallet": "Wallet",
    # "email_2fa" и "phone" — колонок нет
}

HR_NOTION_MAP = {
    "tariff": "VIP",
    "slack_access": "Slack",
    "crm_access": "CRM",
    "notion_access": "Notion",
    # "admin_access" — в Notion колонки нет
}

WALLET_COLUMN = "SquareFi Wallet (USDT TRC20)"
TG_ID_COLUMN = "Telegram ID"
TITLE_COLUMN = "Employee / Candidate"
STATUS_COLUMN = "Status"
EMAIL_COLUMN = "Email address"
SALARY_COLUMN = "Salary"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w.-]+)+")


def extract_email(text: str) -> Optional[str]:
    m = EMAIL_RE.search(text or "")
    return m.group(0) if m else None


def _enabled() -> bool:
    return bool(NOTION_TOKEN and NOTION_DB_ID)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def _request(method: str, path: str, payload: Optional[dict] = None) -> Optional[dict]:
    if not _enabled():
        return None
    url = f"{API}{path}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.request(method, url, headers=_headers(), json=payload) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    log.warning("Notion %s %s → %s: %s", method, path, resp.status, data)
                    return None
                return data
    except Exception as e:
        log.warning("Notion request failed: %s", e)
        return None


async def create_employee_row(name: str) -> Optional[str]:
    """Создаёт строку в таблице: title=name, Status=Onboarding. Возвращает page_id."""
    if not _enabled():
        return None
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            TITLE_COLUMN: {
                "title": [{"text": {"content": name}}]
            },
            STATUS_COLUMN: {
                "status": {"name": "Onboarding"}
            },
        },
    }
    data = await _request("POST", "/pages", payload)
    return data["id"] if data else None


async def set_email(page_id: str, email: str):
    payload = {
        "properties": {
            EMAIL_COLUMN: {"email": email}
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_salary(page_id: str, salary: str):
    payload = {
        "properties": {
            SALARY_COLUMN: {
                "rich_text": [{"text": {"content": salary}}]
            }
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_start_date(page_id: str, iso_date: str):
    """iso_date: 'YYYY-MM-DD'. Если None/пусто — не пишем."""
    if not iso_date:
        return
    payload = {
        "properties": {
            "Start Date": {"date": {"start": iso_date}}
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_comment(page_id: str, text: str):
    payload = {
        "properties": {
            "Comment": {
                "rich_text": [{"text": {"content": text}}]
            }
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_telegram_id(page_id: str, telegram_id: int):
    payload = {
        "properties": {
            TG_ID_COLUMN: {
                "rich_text": [{"text": {"content": str(telegram_id)}}]
            }
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_checkbox(page_id: str, column_name: str, value: bool):
    payload = {
        "properties": {
            column_name: {"checkbox": bool(value)}
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def set_wallet(page_id: str, wallet: str):
    payload = {
        "properties": {
            WALLET_COLUMN: {
                "rich_text": [{"text": {"content": wallet}}]
            }
        }
    }
    await _request("PATCH", f"/pages/{page_id}", payload)


async def sync_emp_check(page_id: Optional[str], key: str, value: bool):
    if not page_id:
        return
    col = EMP_NOTION_MAP.get(key)
    if col:
        await set_checkbox(page_id, col, value)


async def sync_hr_check(page_id: Optional[str], key: str, value: bool):
    if not page_id:
        return
    col = HR_NOTION_MAP.get(key)
    if col:
        await set_checkbox(page_id, col, value)
