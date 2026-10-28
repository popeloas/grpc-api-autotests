"""Сравнение: что отправили — что вернул сервис — что лежит в базе.

При расхождении сообщение показывает все поля, которые не совпали, а не только первое."""
from __future__ import annotations

from autotests.models import library as m

GENRE_CODES = {"GENRE_UNSPECIFIED": 0, "FICTION": 1, "NON_FICTION": 2, "SCIENCE": 3, "POETRY": 4}


def _collect(where: str, checks: dict[str, tuple]) -> list[str]:
    return [f"{where}.{field}: ожидалось {exp!r}, получено {act!r}"
            for field, (act, exp) in checks.items() if act != exp]


def assert_book_matches_body(book: m.Book, body: dict) -> None:
    problems = _collect("api", {
        "author_id": (str(book.author_id), body["author_id"]),
        "title": (book.title, body["title"].strip()),
        "genre": (book.genre.value, body["genre"]),
        "year": (book.year, body["year"]),
        "price.amount": (book.price.amount, body["price"]["amount"]),
        "price.discounted_amount": (book.price.discounted_amount, body["price"]["discounted_amount"]),
        "price.currency": (book.price.currency, body["price"]["currency"]),
        "available": (book.available, body["available"]),
        "tag": (book.tag, body["tag"]),
    })
    assert not problems, "\n".join(problems)


def assert_book_row_matches_body(row: dict | None, body: dict, book_id: str) -> None:
    assert row is not None, f"db.books: запись {book_id} не найдена"
    problems = _collect("db", {
        "author_id": (row["author_id"], body["author_id"]),
        "title": (row["title"], body["title"].strip()),
        "genre": (row["genre"], GENRE_CODES[body["genre"]]),
        "year": (row["year"], body["year"]),
        "price_amount": (row["price_amount"], body["price"]["amount"]),
        "price_discounted": (row["price_discounted"], body["price"]["discounted_amount"]),
        "price_currency": (row["price_currency"], body["price"]["currency"]),
        "available": (bool(row["available"]), body["available"]),
    })
    assert not problems, "\n".join(problems)
