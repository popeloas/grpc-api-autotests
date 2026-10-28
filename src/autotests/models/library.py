"""Модели ответов сервиса (pydantic v2).

extra="forbid": если сервис начнёт возвращать новое поле или переименует старое, модель упадёт
и покажет, какое именно поле поменялось. Это ловит дрейф контракта раньше, чем он сломает клиентов."""
from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Genre(str, Enum):
    UNSPECIFIED = "GENRE_UNSPECIFIED"
    FICTION = "FICTION"
    NON_FICTION = "NON_FICTION"
    SCIENCE = "SCIENCE"
    POETRY = "POETRY"


class SearchState(str, Enum):
    UNSPECIFIED = "SEARCH_STATE_UNSPECIFIED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class Author(Strict):
    id: UUID
    name: str = Field(min_length=1)
    country: str
    birth_year: int = Field(ge=0)
    tag: str


class Price(Strict):
    # int64 в JSON-представлении protobuf приходит строкой — приводим к int
    amount: int = Field(ge=0)
    discounted_amount: int = Field(ge=0)
    currency: str

    @field_validator("amount", "discounted_amount", mode="before")
    @classmethod
    def _int64(cls, v):
        return int(v)


class Book(Strict):
    id: UUID
    author_id: UUID
    title: str = Field(min_length=1)
    genre: Genre
    year: int
    price: Price
    available: bool
    tag: str


class DeleteResponse(Strict):
    pass


class StartSearchResponse(Strict):
    search_id: UUID


class SearchStatus(Strict):
    search_id: UUID
    state: SearchState


class SearchResults(Strict):
    search_id: UUID
    books: list[Book]
