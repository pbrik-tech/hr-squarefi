"""SQLite-хранилище FSM для aiogram 3 — переживает рестарты контейнера."""
import json
import os
import sqlite3
from typing import Any, Dict, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("DB_PATH", "bot.db")
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_state (
                    key TEXT PRIMARY KEY,
                    state TEXT,
                    data TEXT
                )
                """
            )

    @staticmethod
    def _k(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id or 0}"

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        if isinstance(state, State):
            state_str = state.state
        else:
            state_str = state if state else None
        with sqlite3.connect(self.db_path) as c:
            if state_str is None:
                # Если и data нет, удаляем запись
                row = c.execute(
                    "SELECT data FROM fsm_state WHERE key = ?", (self._k(key),)
                ).fetchone()
                if not row or not row[0] or row[0] == "{}":
                    c.execute("DELETE FROM fsm_state WHERE key = ?", (self._k(key),))
                else:
                    c.execute(
                        "UPDATE fsm_state SET state = NULL WHERE key = ?",
                        (self._k(key),),
                    )
            else:
                c.execute(
                    "INSERT INTO fsm_state (key, state) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET state = excluded.state",
                    (self._k(key), state_str),
                )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        with sqlite3.connect(self.db_path) as c:
            row = c.execute(
                "SELECT state FROM fsm_state WHERE key = ?", (self._k(key),)
            ).fetchone()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        payload = json.dumps(data) if data else "{}"
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO fsm_state (key, data) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
                (self._k(key), payload),
            )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as c:
            row = c.execute(
                "SELECT data FROM fsm_state WHERE key = ?", (self._k(key),)
            ).fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    async def close(self) -> None:
        pass
