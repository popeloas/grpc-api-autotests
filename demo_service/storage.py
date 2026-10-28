"""Хранилище демо-сервиса: SQLite-файл.

Автотесты читают этот файл напрямую (только чтение), чтобы сверить: что отправили → что вернул
сервис → что легло в базу."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS authors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    birth_year INTEGER NOT NULL DEFAULT 0,
    tag TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL REFERENCES authors(id),
    title TEXT NOT NULL,
    genre INTEGER NOT NULL DEFAULT 0,
    year INTEGER NOT NULL DEFAULT 0,
    price_amount INTEGER NOT NULL DEFAULT 0,
    price_discounted INTEGER NOT NULL DEFAULT 0,
    price_currency TEXT NOT NULL DEFAULT '',
    available INTEGER NOT NULL DEFAULT 0,
    tag TEXT NOT NULL DEFAULT ''
);
"""


class Storage:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()
