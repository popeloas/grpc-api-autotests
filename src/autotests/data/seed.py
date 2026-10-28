"""Создание и удаление тестовых данных через API сервиса.

Тест получает и тело запроса, и ответ сервиса. После теста удаляется только то, что он создал.
Если удалить не получилось — тест помечается ошибкой: мусор на стенде не остаётся незамеченным."""
from __future__ import annotations

from dataclasses import dataclass, field

from autotests.clients.grpc_json import GrpcError
from autotests.clients.library_api import CatalogApi
from autotests.data import factories
from autotests.models import library as m


@dataclass
class SeededAuthor:
    body: dict
    model: m.Author

    @property
    def id(self) -> str:
        return str(self.model.id)


@dataclass
class SeededBook:
    body: dict
    model: m.Book
    author: SeededAuthor

    @property
    def id(self) -> str:
        return str(self.model.id)


@dataclass
class CatalogSeeder:
    api: CatalogApi
    _books: list[str] = field(default_factory=list)
    _authors: list[str] = field(default_factory=list)

    def author(self, **overrides) -> SeededAuthor:
        body = factories.author_payload(**overrides)
        model = self.api.create_author(body)
        self._authors.append(str(model.id))
        return SeededAuthor(body=body, model=model)

    def book(self, author: SeededAuthor | None = None, **overrides) -> SeededBook:
        author = author or self.author()
        body = factories.book_payload(author.id, **overrides)
        model = self.api.upsert_book(body)
        self.track_book(str(model.id))
        return SeededBook(body=body, model=model, author=author)

    # для тестов, которые создают данные сами, но хотят гарантированной уборки
    def track_book(self, book_id: str) -> None:
        if book_id not in self._books:
            self._books.append(book_id)

    def track_author(self, author_id: str) -> None:
        if author_id not in self._authors:
            self._authors.append(author_id)

    def cleanup(self) -> list[str]:
        """Сначала книги, потом авторы (автора с книгами сервис не удаляет)."""
        problems: list[str] = []
        for ids, delete in ((self._books, self.api.delete_book), (self._authors, self.api.delete_author)):
            for _id in reversed(ids):
                try:
                    delete(_id)
                except GrpcError as e:
                    if e.code.name != "NOT_FOUND":
                        problems.append(str(e))
            ids.clear()
        return problems
