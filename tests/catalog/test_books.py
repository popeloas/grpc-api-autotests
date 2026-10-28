"""Книги: полный цикл (создать → прочитать → изменить → удалить), сверка с базой, поток, валидация."""
from __future__ import annotations

import uuid

import grpc
import pytest

from autotests.assertions import assert_book_matches_body, assert_book_row_matches_body
from autotests.clients.grpc_json import GrpcError
from autotests.data import factories
from autotests.errors import CatalogErrors, assert_grpc_error
from autotests.models import library as m
from autotests.steps import step

pytestmark = [pytest.mark.writes]


@pytest.mark.smoke
class TestPositive:
    def test_create_book_matches_request(self, book):
        assert_book_matches_body(book.model, book.body)

    def test_get_book(self, catalog, book):
        assert catalog.get_book(book.id) == book.model

    @pytest.mark.needs_db
    def test_request_response_db_match(self, catalog, db, book):
        """Что отправили = что вернул сервис = что лежит в базе."""
        with step("ответ сервиса совпадает с запросом"):
            assert_book_matches_body(book.model, book.body)
        with step("запись в базе совпадает с запросом"):
            assert_book_row_matches_body(db.book(book.id), book.body, book.id)

    def test_update_book(self, catalog, book):
        changed = {**book.body, "id": book.id, "title": f"{book.body['title']} (2-е изд.)", "available": False}
        updated = catalog.upsert_book(changed)
        assert updated.id == book.model.id, "upsert с id должен обновить, а не создать новую книгу"
        assert_book_matches_body(updated, changed)
        assert catalog.get_book(book.id) == updated

    def test_delete_book(self, catalog, book):
        catalog.delete_book(book.id)
        with pytest.raises(GrpcError) as err:
            catalog.get_book(book.id)
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, CatalogErrors.BOOK_NOT_FOUND)

    def test_list_books_by_author_stream(self, catalog, seeder, author):
        books = [seeder.book(author) for _ in range(3)]
        streamed = catalog.list_books_by_author(author.id)
        assert {b.id for b in streamed} == {b.model.id for b in books}
        assert [b.title for b in streamed] == sorted(b.title for b in streamed), "поток должен быть по алфавиту"

    def test_list_books_unknown_author_is_empty(self, catalog):
        assert catalog.list_books_by_author(str(uuid.uuid4())) == []


@pytest.mark.regress
class TestBusinessRules:
    def test_discount_not_above_price(self, book):
        price = book.model.price
        assert price.discounted_amount <= price.amount


@pytest.mark.regress
class TestNegative:
    def test_title_required(self, catalog, author):
        with pytest.raises(GrpcError) as err:
            catalog.upsert_book(factories.book_payload(author.id, title="  "))
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.TITLE_REQUIRED)

    def test_unknown_author(self, catalog):
        with pytest.raises(GrpcError) as err:
            catalog.upsert_book(factories.book_payload(str(uuid.uuid4())))
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, CatalogErrors.AUTHOR_NOT_FOUND)

    def test_invalid_book_id(self, catalog, author):
        with pytest.raises(GrpcError) as err:
            catalog.upsert_book(factories.book_payload(author.id, id="123"))
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.INVALID_BOOK_ID)

    def test_get_unknown_book(self, catalog):
        with pytest.raises(GrpcError) as err:
            catalog.get_book(str(uuid.uuid4()))
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, CatalogErrors.BOOK_NOT_FOUND)

    def test_get_garbage_id(self, catalog):
        with pytest.raises(GrpcError) as err:
            catalog.get_book("not-a-uuid")
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.INVALID_BOOK_ID)


@pytest.mark.regress
@pytest.mark.known_bug
class TestKnownBugs:
    """Тест проверяет, как ДОЛЖНО быть. Пока баг не исправлен — xfail; исправят — xfail(strict)
    превратится в падение XPASS, и тест нужно перенести в обычную группу."""

    @pytest.mark.xfail(strict=True, reason="БАГ DEMO-1: сервис сохраняет цену со скидкой больше цены")
    def test_discount_above_price_rejected(self, catalog, seeder, author):
        body = factories.book_payload(author.id, price={"amount": 1000, "discounted_amount": 5000, "currency": "RUB"})
        try:
            created = catalog.upsert_book(body)
        except GrpcError as e:
            assert_grpc_error(e, grpc.StatusCode.INVALID_ARGUMENT)
            return
        seeder.track_book(str(created.id))
        pytest.fail(f"книга сохранена с discounted_amount > amount: {created.price}")

    @pytest.mark.xfail(strict=True, reason="БАГ DEMO-2: GetBook с пустым id → INTERNAL вместо INVALID_ARGUMENT")
    def test_get_book_empty_id(self, catalog):
        with pytest.raises(GrpcError) as err:
            catalog.get_book("")
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.INVALID_BOOK_ID)


@pytest.mark.regress
def test_genre_enum_roundtrip(catalog, seeder, author):
    """Все жанры сохраняются и возвращаются без потерь."""
    for genre in (g for g in m.Genre if g is not m.Genre.UNSPECIFIED):
        created = seeder.book(author, genre=genre.value)
        assert created.model.genre is genre
