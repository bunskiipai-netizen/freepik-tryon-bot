"""SQLite storage: user whitelist, admin status, dan saldo token."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    is_admin: bool
    tokens: int
    username: str | None
    full_name: str | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    tokens      INTEGER NOT NULL DEFAULT 0,
    username    TEXT,
    full_name   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS token_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    delta       INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    actor_id    INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Storage:
    """SQLite-backed user + token store.

    Methods are synchronous; the bot uses ``asyncio.to_thread`` to keep the
    event loop responsive.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    _COLS = "user_id, is_admin, tokens, username, full_name"

    def _row_to_user(self, row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            user_id=int(row["user_id"]),
            is_admin=bool(row["is_admin"]),
            tokens=int(row["tokens"]),
            username=row["username"],
            full_name=row["full_name"],
        )

    # ---- queries ----------------------------------------------------------

    def get_user(self, user_id: int) -> UserRecord | None:
        cur = self._conn.execute(
            f"SELECT {self._COLS} FROM users WHERE user_id = ?", (user_id,)
        )
        return self._row_to_user(cur.fetchone())

    def list_users(self) -> list[UserRecord]:
        cur = self._conn.execute(
            f"SELECT {self._COLS} FROM users ORDER BY is_admin DESC, user_id ASC"
        )
        return [u for u in (self._row_to_user(r) for r in cur.fetchall()) if u is not None]

    def has_admin(self) -> bool:
        cur = self._conn.execute("SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1")
        return cur.fetchone() is not None

    # ---- mutations --------------------------------------------------------

    def upsert_user(
        self,
        user_id: int,
        *,
        is_admin: bool | None = None,
        username: str | None = None,
        full_name: str | None = None,
    ) -> UserRecord:
        existing = self.get_user(user_id)
        if existing is None:
            self._conn.execute(
                "INSERT INTO users (user_id, is_admin, username, full_name) "
                "VALUES (?, ?, ?, ?)",
                (user_id, 1 if is_admin else 0, username, full_name),
            )
        else:
            updates: list[str] = ["updated_at = datetime('now')"]
            values: list[object] = []
            if is_admin is not None:
                updates.append("is_admin = ?")
                values.append(1 if is_admin else 0)
            if username is not None:
                updates.append("username = ?")
                values.append(username)
            if full_name is not None:
                updates.append("full_name = ?")
                values.append(full_name)
            values.append(user_id)
            self._conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
                values,
            )
        self._conn.commit()
        record = self.get_user(user_id)
        assert record is not None
        return record

    def remove_user(self, user_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def ensure_admins(self, user_ids: Iterable[int]) -> None:
        for uid in user_ids:
            self.upsert_user(uid, is_admin=True)

    # ---- tokens -----------------------------------------------------------

    def grant_tokens(self, user_id: int, amount: int, *, actor_id: int | None) -> int:
        """Add ``amount`` tokens (can be negative). Returns new balance."""
        if amount == 0:
            user = self.get_user(user_id)
            return user.tokens if user else 0
        self.upsert_user(user_id)
        self._conn.execute(
            "UPDATE users SET tokens = tokens + ?, updated_at = datetime('now') "
            "WHERE user_id = ?",
            (amount, user_id),
        )
        self._conn.execute(
            "INSERT INTO token_audit (user_id, delta, reason, actor_id) "
            "VALUES (?, ?, ?, ?)",
            (user_id, amount, "grant" if amount > 0 else "deduct_admin", actor_id),
        )
        self._conn.commit()
        user = self.get_user(user_id)
        return user.tokens if user else 0

    def consume_token(self, user_id: int, *, reason: str = "image_delivered") -> int | None:
        """Atomically deduct one token. Returns new balance or ``None`` if empty."""
        user = self.get_user(user_id)
        if user is None or user.tokens <= 0:
            return None
        cur = self._conn.execute(
            "UPDATE users SET tokens = tokens - 1, updated_at = datetime('now') "
            "WHERE user_id = ? AND tokens > 0",
            (user_id,),
        )
        if cur.rowcount == 0:
            self._conn.commit()
            return None
        self._conn.execute(
            "INSERT INTO token_audit (user_id, delta, reason, actor_id) "
            "VALUES (?, -1, ?, NULL)",
            (user_id, reason),
        )
        self._conn.commit()
        user = self.get_user(user_id)
        return user.tokens if user else 0

    def get_balance(self, user_id: int) -> int:
        user = self.get_user(user_id)
        return user.tokens if user else 0
