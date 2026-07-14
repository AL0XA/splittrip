"""Хранилище на SQLite (stdlib): пользователи, события, участники, траты.

Все денежные суммы хранятся в копейках (INTEGER).
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
import time

from .config import DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
    return _conn


def init_db() -> None:
    conn = get_conn()
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                currency   TEXT    NOT NULL DEFAULT '₽',
                owner_id   INTEGER NOT NULL,
                code       TEXT    NOT NULL UNIQUE,
                created_at REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS members (
                event_id  INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                user_id   INTEGER NOT NULL,
                joined_at REAL    NOT NULL,
                PRIMARY KEY (event_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                payer_id    INTEGER NOT NULL,
                amount      INTEGER NOT NULL,           -- копейки
                description TEXT    NOT NULL,
                created_at  REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expense_shares (
                expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL,
                PRIMARY KEY (expense_id, user_id)
            );
            """
        )
        conn.commit()


# ---------- Пользователи ----------

def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username,
                                               first_name = excluded.first_name
            """,
            (user_id, username, first_name),
        )
        conn.commit()


def get_user(user_id: int) -> dict | None:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ---------- События ----------

def create_event(title: str, owner_id: int, currency: str = "₽") -> dict:
    conn = get_conn()
    now = time.time()
    code = secrets.token_urlsafe(6)
    with _lock:
        cur = conn.execute(
            "INSERT INTO events (title, currency, owner_id, code, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, currency, owner_id, code, now),
        )
        event_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO members (event_id, user_id, joined_at) VALUES (?, ?, ?)",
            (event_id, owner_id, now),
        )
        conn.commit()
    return get_event(event_id)  # type: ignore[return-value]


def get_event(event_id: int) -> dict | None:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def get_event_by_code(code: str) -> dict | None:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM events WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def list_user_events(user_id: int) -> list[dict]:
    conn = get_conn()
    with _lock:
        rows = conn.execute(
            """
            SELECT e.*, (SELECT COUNT(*) FROM members m2 WHERE m2.event_id = e.id) AS member_count
              FROM events e
              JOIN members m ON m.event_id = e.id
             WHERE m.user_id = ?
             ORDER BY e.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- Участники ----------

def add_member(event_id: int, user_id: int) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT OR IGNORE INTO members (event_id, user_id, joined_at) VALUES (?, ?, ?)",
            (event_id, user_id, time.time()),
        )
        conn.commit()


def is_member(event_id: int, user_id: int) -> bool:
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT 1 FROM members WHERE event_id = ? AND user_id = ?", (event_id, user_id)
        ).fetchone()
    return row is not None


def list_members(event_id: int) -> list[dict]:
    conn = get_conn()
    with _lock:
        rows = conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name
              FROM members m
              JOIN users u ON u.user_id = m.user_id
             WHERE m.event_id = ?
             ORDER BY m.joined_at
            """,
            (event_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- Траты ----------

def add_expense(event_id: int, payer_id: int, amount: int,
                description: str, participant_ids: list[int]) -> int:
    conn = get_conn()
    now = time.time()
    with _lock:
        cur = conn.execute(
            "INSERT INTO expenses (event_id, payer_id, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, payer_id, amount, description, now),
        )
        expense_id = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO expense_shares (expense_id, user_id) VALUES (?, ?)",
            [(expense_id, uid) for uid in participant_ids],
        )
        conn.commit()
    return expense_id


def list_expenses(event_id: int) -> list[dict]:
    conn = get_conn()
    with _lock:
        exp_rows = conn.execute(
            "SELECT * FROM expenses WHERE event_id = ? ORDER BY created_at DESC", (event_id,)
        ).fetchall()
        share_rows = conn.execute(
            """
            SELECT s.expense_id, s.user_id
              FROM expense_shares s
              JOIN expenses e ON e.id = s.expense_id
             WHERE e.event_id = ?
            """,
            (event_id,),
        ).fetchall()

    shares: dict[int, list[int]] = {}
    for r in share_rows:
        shares.setdefault(r["expense_id"], []).append(r["user_id"])

    result = []
    for r in exp_rows:
        d = dict(r)
        d["participants"] = shares.get(r["id"], [])
        result.append(d)
    return result


def get_expense(expense_id: int) -> dict | None:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return dict(row) if row else None


def delete_expense(expense_id: int) -> None:
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
