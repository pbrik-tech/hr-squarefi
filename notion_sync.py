import logging
import os
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
    "email": "Email",
    "wallet": "Wallet",
    # "phone" — в Notion колонки нет
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
    """Создаёт строку в таблице с заголовком = name. Возвращает page_id."""
    if not _enabled():
        return None
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            TITLE_COLUMN: {
                "title": [{"text": {"content": name}}]
            }
        },
    }
    data = await _request("POST", "/pages", payload)
    return data["id"] if data else None


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
