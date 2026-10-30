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
# База: HR / Team (https://app.notion.com/p/1fdfa0f74075475e8f040483ca5a4bba),
# с 10.2026 заменила старую HR / Employments.
EMP_NOTION_MAP = {
    "verification": "SumSub",
    "nda": "NDA",
    "contract": "Agreement",
    "gmail_access": "Email access",  # галочка ставится когда доступ к почте выдан
    "wallet": "Wallet issued",
    "fleet": "Fleet MDM",
    # "email_2fa" и "phone" — колонок нет
}

HR_NOTION_MAP = {
    "tariff": "VIP",
    "slack_access": "Slack access",
    "crm_access": "CRM access",
    "notion_access": "Notion access",
    # "admin_access" — в Notion колонки нет
}

WALLET_COLUMN = "Wallet (USDT TRC20)"
TG_ID_COLUMN = "Telegram ID"
TITLE_COLUMN = "Name"
STATUS_COLUMN = "Status"
EMAIL_COLUMN = "Email"
SALARY_COLUMN = "Salary"
SALARY_TYPE_COLUMN = "Salary Type"
TELEGRAM_COLUMN = "Telegram"
PHONE_COLUMN = "Phone"
SUMSUB_LINK_COLUMN = "SumSub Link"
PHOTO_COLUMN = "Photo"

STATUS_NEW = "NEW"
STATUS_ON_PROBATION = "On Probation"
SALARY_TYPE_CRYPTO = "Crypto"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w.-]+)+")


def extract_email(text: str) -> Optional[str]:
    m = EMAIL_RE.search(text or "")
    return m.group(0) if m else None


URL_RE = re.compile(r"https?://\S+")
PHONE_RE = re.compile(r"\+?\d[\d\s()\-]{6,}\d")


def extract_url(text: str) -> Optional[str]:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,;)") if m else None


def extract_phone(text: str) -> Optional[str]:
    m = PHONE_RE.search(text or "")
    return m.group(0).strip() if m else None


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
    """Создаёт строку в таблице: title=name, Status=NEW. Возвращает page_id."""
    if not _enabled():
        return None
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            TITLE_COLUMN: {
                "title": [{"text": {"content": name}}]
            },
            STATUS_COLUMN: {
                "status": {"name": STATUS_NEW}
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
    """В таблице Team нет колонки Comment — пишем комментарий абзацем в тело страницы."""
    payload = {
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            }
        ]
    }
    await _request("PATCH", f"/blocks/{page_id}/children", payload)


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


async def _set_props(page_id: Optional[str], props: dict):
    if not page_id:
        return
    await _request("PATCH", f"/pages/{page_id}", {"properties": props})


async def set_telegram(page_id: Optional[str], telegram_id: int, username: Optional[str]):
    """Telegram ID + @username (колонка Telegram)."""
    props = {TG_ID_COLUMN: {"rich_text": [{"text": {"content": str(telegram_id)}}]}}
    if username:
        props[TELEGRAM_COLUMN] = {"rich_text": [{"text": {"content": f"@{username}"}}]}
    await _set_props(page_id, props)


async def set_phone(page_id: Optional[str], phone: str):
    await _set_props(page_id, {PHONE_COLUMN: {"phone_number": phone}})


async def set_sumsub_link(page_id: Optional[str], url: str):
    await _set_props(page_id, {SUMSUB_LINK_COLUMN: {"url": url}})


async def set_salary_type_crypto(page_id: Optional[str]):
    await _set_props(page_id, {SALARY_TYPE_COLUMN: {"select": {"name": SALARY_TYPE_CRYPTO}}})


async def set_status(page_id: Optional[str], status: str):
    await _set_props(page_id, {STATUS_COLUMN: {"status": {"name": status}}})


async def upload_photo(page_id: Optional[str], data: bytes, filename: str = "photo.jpg"):
    """Загружает фото в Notion (File Upload API) и кладёт в колонку Photo."""
    if not page_id or not _enabled():
        return
    created = await _request(
        "POST", "/file_uploads", {"filename": filename, "content_type": "image/jpeg"}
    )
    if not created:
        return
    upload_id = created["id"]
    form = aiohttp.FormData()
    form.add_field("file", data, filename=filename, content_type="image/jpeg")
    headers = {k: v for k, v in _headers().items() if k != "Content-Type"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{API}/file_uploads/{upload_id}/send", headers=headers, data=form
            ) as resp:
                if resp.status >= 400:
                    log.warning("Notion photo upload → %s: %s", resp.status, await resp.text())
                    return
    except Exception as e:
        log.warning("Notion photo upload failed: %s", e)
        return
    await _set_props(page_id, {
        PHOTO_COLUMN: {"files": [{
            "type": "file_upload",
            "file_upload": {"id": upload_id},
            "name": filename,
        }]}
    })
