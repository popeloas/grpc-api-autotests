"""Тела запросов с реалистичными случайными данными.

Каждая запись помечена tag="qa-autotest" и уникальным RUN_ID: по метке остатки упавших прогонов
находятся и удаляются, а параллельные прогоны не мешают друг другу."""
from __future__ import annotations

import os
import random
import uuid

from faker import Faker

fake = Faker("ru_RU")
QA_TAG = "qa-autotest"
RUN_ID = os.getenv("QA_RUN_ID") or uuid.uuid4().hex[:8]


def author_payload(**overrides) -> dict:
    body = {
        "name": f"QA {fake.name()} {RUN_ID}",
        "country": fake.country(),
        "birth_year": random.randint(1800, 2000),
        "tag": QA_TAG,
    }
    body.update(overrides)
    return body


def book_payload(author_id: str, **overrides) -> dict:
    amount = random.randint(30_000, 300_000)
    body = {
        "author_id": author_id,
        "title": f"QA {fake.catch_phrase()} {RUN_ID} {uuid.uuid4().hex[:6]}",
        "genre": random.choice(["FICTION", "NON_FICTION", "SCIENCE", "POETRY"]),
        "year": random.randint(1900, 2025),
        "price": {"amount": amount, "discounted_amount": amount - random.randint(0, amount // 3), "currency": "RUB"},
        "available": True,
        "tag": QA_TAG,
    }
    body.update(overrides)
    return body
