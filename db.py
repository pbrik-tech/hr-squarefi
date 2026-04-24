import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "bot.db")


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                token TEXT PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                hr_checklist TEXT NOT NULL DEFAULT '{}',
                emp_checklist TEXT NOT NULL DEFAULT '{}',
                tron_wallet TEXT,
                flow_step TEXT DEFAULT 'new',
                notion_page_id TEXT,
                last_action_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT,
                actor TEXT NOT NULL,
                event TEXT NOT NULL,
                payload TEXT,
                ts TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_token ON audit_log(token);
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);

            CREATE TABLE IF NOT EXISTS messages_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT,
                direction TEXT NOT NULL,
                text TEXT,
                ts TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_msg_token ON messages_log(token);
            """
        )
        # idempotent column add
        cols = [r[1] for r in c.execute("PRAGMA table_info(employees);").fetchall()]
        if "flow_step" not in cols:
            c.execute("ALTER TABLE employees ADD COLUMN flow_step TEXT DEFAULT 'new';")
        if "notion_page_id" not in cols:
            c.execute("ALTER TABLE employees ADD COLUMN notion_page_id TEXT;")
        if "last_action_at" not in cols:
            c.execute("ALTER TABLE employees ADD COLUMN last_action_at TEXT;")


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def create_employee(name: str) -> str:
    token = secrets.token_urlsafe(9)
    with _conn() as c:
        c.execute(
            "INSERT INTO employees (token, name, created_at, flow_step) VALUES (?, ?, ?, 'new')",
            (token, name, datetime.utcnow().isoformat()),
        )
    return token


def create_employee_self(name: str, telegram_id: int) -> str:
    """Сотрудник сам написал первым — создаём карточку с TG ID, ждём апрув HR."""
    token = secrets.token_urlsafe(9)
    with _conn() as c:
        # Освобождаем TG ID у старых записей (если было)
        c.execute(
            "UPDATE employees SET telegram_id = NULL WHERE telegram_id = ?",
            (telegram_id,),
        )
        c.execute(
            "INSERT INTO employees (token, name, created_at, flow_step, telegram_id) "
            "VALUES (?, ?, ?, 'pending_approval', ?)",
            (token, name, datetime.utcnow().isoformat(), telegram_id),
        )
    return token


def delete_employee(token: str):
    with _conn() as c:
        c.execute("DELETE FROM employees WHERE token = ?", (token,))


def link_employee(token: str, telegram_id: int) -> bool:
    with _conn() as c:
        # Освобождаем этот telegram_id у других записей (на случай тестирования с одного аккаунта)
        c.execute(
            "UPDATE employees SET telegram_id = NULL "
            "WHERE telegram_id = ? AND token != ?",
            (telegram_id, token),
        )
        cur = c.execute(
            "UPDATE employees SET telegram_id = ?, flow_step = 'joined' "
            "WHERE token = ? AND telegram_id IS NULL",
            (telegram_id, token),
        )
        return cur.rowcount > 0


def get_by_token(token: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM employees WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def get_by_tg(telegram_id: int):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM employees WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return dict(row) if row else None


def list_all():
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM employees ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def toggle_check(token: str, kind: str, key: str) -> dict:
    field = "hr_checklist" if kind == "hr" else "emp_checklist"
    with _conn() as c:
        row = c.execute(
            f"SELECT {field} FROM employees WHERE token = ?", (token,)
        ).fetchone()
        data = json.loads(row[0] or "{}")
        data[key] = not data.get(key, False)
        c.execute(
            f"UPDATE employees SET {field} = ? WHERE token = ?",
            (json.dumps(data), token),
        )
    return data


def set_check(token: str, kind: str, key: str, value: bool = True) -> dict:
    field = "hr_checklist" if kind == "hr" else "emp_checklist"
    with _conn() as c:
        row = c.execute(
            f"SELECT {field} FROM employees WHERE token = ?", (token,)
        ).fetchone()
        data = json.loads(row[0] or "{}")
        data[key] = value
        c.execute(
            f"UPDATE employees SET {field} = ? WHERE token = ?",
            (json.dumps(data), token),
        )
    return data


def get_checks(token: str, kind: str) -> dict:
    emp = get_by_token(token)
    if not emp:
        return {}
    return json.loads(emp["hr_checklist" if kind == "hr" else "emp_checklist"] or "{}")


def set_wallet(token: str, wallet: str):
    with _conn() as c:
        c.execute(
            "UPDATE employees SET tron_wallet = ? WHERE token = ?", (wallet, token)
        )


def set_step(token: str, step: str):
    with _conn() as c:
        c.execute("UPDATE employees SET flow_step = ? WHERE token = ?", (step, token))


def set_notion_page_id(token: str, page_id: str):
    with _conn() as c:
        c.execute(
            "UPDATE employees SET notion_page_id = ? WHERE token = ?", (page_id, token)
        )


# ---- Audit log & messages log ----

def audit(token: str, actor: str, event: str, payload: dict = None):
    """Запись в журнал действий. Также обновляет last_action_at у сотрудника."""
    ts = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO audit_log (token, actor, event, payload, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (token, actor, event, json.dumps(payload, ensure_ascii=False) if payload else None, ts),
        )
        if token:
            c.execute(
                "UPDATE employees SET last_action_at = ? WHERE token = ?", (ts, token)
            )


def log_msg(token: str, direction: str, text: str):
    """Журнал сообщений. direction: bot_to_emp / emp_to_bot / bot_to_hr / hr_to_bot"""
    if not text:
        return
    with _conn() as c:
        c.execute(
            "INSERT INTO messages_log (token, direction, text, ts) "
            "VALUES (?, ?, ?, ?)",
            (token, direction, text[:4000], datetime.utcnow().isoformat()),
        )


def get_audit_log(token: str, limit: int = 30):
    with _conn() as c:
        rows = c.execute(
            "SELECT event, actor, payload, ts FROM audit_log "
            "WHERE token = ? ORDER BY id DESC LIMIT ?",
            (token, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages_log(token: str, limit: int = 30):
    with _conn() as c:
        rows = c.execute(
            "SELECT direction, text, ts FROM messages_log "
            "WHERE token = ? ORDER BY id DESC LIMIT ?",
            (token, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stale_employees(days: int = 3):
    """Сотрудники без движения > days дней, ещё не завершившие онбординг."""
    threshold = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM employees "
            "WHERE flow_step != 'flow_done' "
            "AND (last_action_at IS NULL OR last_action_at < ?) "
            "ORDER BY COALESCE(last_action_at, created_at)",
            (threshold,),
        ).fetchall()
    return [dict(r) for r in rows]
