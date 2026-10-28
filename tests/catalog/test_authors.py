"""Авторы: создание, чтение, удаление и валидация входных данных."""
from __future__ import annotations

import uuid

import grpc
import pytest

from autotests.clients.grpc_json import GrpcError
from autotests.data import factories
from autotests.errors import CatalogErrors, assert_grpc_error

pytestmark = [pytest.mark.writes]


@pytest.mark.smoke
class TestPositive:
    def test_create_and_get_author(self, seeder, catalog):
        created = seeder.author()
        got = catalog.get_author(created.id)
        assert got == created.model
        assert got.name == created.body["name"]
        assert got.tag == factories.QA_TAG

    def test_name_is_trimmed(self, seeder):
        created = seeder.author(name="   QA Лев Пробелов   ")
        assert created.model.name == "QA Лев Пробелов"

    def test_delete_author(self, seeder, catalog):
        created = seeder.author()
        catalog.delete_author(created.id)
        with pytest.raises(GrpcError) as err:
            catalog.get_author(created.id)
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, CatalogErrors.AUTHOR_NOT_FOUND)


@pytest.mark.regress
class TestNegative:
    @pytest.mark.parametrize("name", ["", "   "], ids=["empty", "spaces"])
    def test_name_required(self, catalog, name):
        with pytest.raises(GrpcError) as err:
            catalog.create_author(factories.author_payload(name=name))
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.NAME_REQUIRED)

    @pytest.mark.parametrize("year", [-1, 3000], ids=["negative", "future"])
    def test_birth_year_range(self, catalog, year):
        with pytest.raises(GrpcError) as err:
            catalog.create_author(factories.author_payload(birth_year=year))
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.BIRTH_YEAR_OUT_OF_RANGE)

    @pytest.mark.parametrize("author_id", ["", "not-a-uuid"], ids=["empty", "garbage"])
    def test_get_invalid_id(self, catalog, author_id):
        with pytest.raises(GrpcError) as err:
            catalog.get_author(author_id)
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, CatalogErrors.INVALID_AUTHOR_ID)

    def test_get_unknown(self, catalog):
        with pytest.raises(GrpcError) as err:
            catalog.get_author(str(uuid.uuid4()))
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, CatalogErrors.AUTHOR_NOT_FOUND)

    def test_cannot_delete_author_with_books(self, catalog, book):
        with pytest.raises(GrpcError) as err:
            catalog.delete_author(book.author.id)
        assert_grpc_error(err, grpc.StatusCode.FAILED_PRECONDITION, CatalogErrors.AUTHOR_HAS_BOOKS)
        assert catalog.get_author(book.author.id) == book.author.model, "автор должен остаться"
