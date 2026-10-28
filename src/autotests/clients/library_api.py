"""Типизированная обёртка над gRPC: тесты работают с моделями, а не с dict.

Каждый вызов — отдельный шаг в Allure, ответ сразу проходит через pydantic-модель."""
from __future__ import annotations

from autotests.clients.grpc_json import GrpcJsonClient
from autotests.models import library as m
from autotests.steps import step

CATALOG = "library.v1.CatalogService"
SEARCH = "library.v1.SearchService"


class CatalogApi:
    def __init__(self, grpc: GrpcJsonClient):
        self.grpc = grpc

    def create_author(self, body: dict) -> m.Author:
        with step(f"CreateAuthor «{body.get('name')}»"):
            return m.Author.model_validate(self.grpc.call(f"{CATALOG}/CreateAuthor", body))

    def get_author(self, author_id: str) -> m.Author:
        with step(f"GetAuthor {author_id}"):
            return m.Author.model_validate(self.grpc.call(f"{CATALOG}/GetAuthor", {"id": author_id}))

    def delete_author(self, author_id: str) -> None:
        with step(f"DeleteAuthor {author_id}"):
            m.DeleteResponse.model_validate(self.grpc.call(f"{CATALOG}/DeleteAuthor", {"id": author_id}))

    def upsert_book(self, body: dict) -> m.Book:
        with step(f"UpsertBook «{body.get('title')}»"):
            return m.Book.model_validate(self.grpc.call(f"{CATALOG}/UpsertBook", body))

    def get_book(self, book_id: str) -> m.Book:
        with step(f"GetBook {book_id!r}"):
            return m.Book.model_validate(self.grpc.call(f"{CATALOG}/GetBook", {"id": book_id}))

    def delete_book(self, book_id: str) -> None:
        with step(f"DeleteBook {book_id}"):
            m.DeleteResponse.model_validate(self.grpc.call(f"{CATALOG}/DeleteBook", {"id": book_id}))

    def list_books_by_author(self, author_id: str) -> list[m.Book]:
        with step(f"ListBooksByAuthor {author_id} (stream)"):
            items = self.grpc.call(f"{CATALOG}/ListBooksByAuthor", {"author_id": author_id})
            return [m.Book.model_validate(i) for i in items]


class SearchApi:
    def __init__(self, grpc: GrpcJsonClient):
        self.grpc = grpc

    def start(self, query: str, genre: m.Genre | None = None) -> m.StartSearchResponse:
        body = {"query": query}
        if genre:
            body["genre"] = genre.value
        with step(f"StartSearch {body}"):
            return m.StartSearchResponse.model_validate(self.grpc.call(f"{SEARCH}/StartSearch", body))

    def status(self, search_id: str) -> m.SearchStatus:
        return m.SearchStatus.model_validate(self.grpc.call(f"{SEARCH}/GetSearchStatus", {"search_id": search_id}))

    def results(self, search_id: str) -> m.SearchResults:
        with step(f"GetSearchResults {search_id}"):
            return m.SearchResults.model_validate(
                self.grpc.call(f"{SEARCH}/GetSearchResults", {"search_id": search_id})
            )
