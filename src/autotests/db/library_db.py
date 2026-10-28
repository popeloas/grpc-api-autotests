"""Прямое чтение базы сервиса — для проверки «что легло в БД».

Только чтение (mode=ro): тесты никогда не пишут в базу в обход API."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from autotests.data.factories import QA_TAG


class LibraryDb:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def book(self, book_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None

    def author(self, author_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM authors WHERE id = ?", (author_id,)).fetchone()
        return dict(row) if row else None

    def qa_leftovers(self) -> dict[str, list[str]]:
        """Записи с меткой qa-autotest — остатки прошлых прогонов."""
        return {
            "books": [r[0] for r in self._conn.execute("SELECT id FROM books WHERE tag = ?", (QA_TAG,))],
            "authors": [r[0] for r in self._conn.execute("SELECT id FROM authors WHERE tag = ?", (QA_TAG,))],
        }

    def close(self) -> None:
        self._conn.close()
