"""Контракт: какие сервисы и методы опубликованы и совпадают ли модели тестов со схемой сервиса.

Падает, если метод удалили или переименовали, или поменялся состав полей ответа."""
from __future__ import annotations

import pytest

from autotests.clients.library_api import CATALOG, SEARCH
from autotests.contract import schema_diff
from autotests.models import library as m

pytestmark = [pytest.mark.contract, pytest.mark.smoke]

EXPECTED = {
    CATALOG: {"CreateAuthor", "GetAuthor", "DeleteAuthor", "UpsertBook", "GetBook", "DeleteBook",
              "ListBooksByAuthor"},
    SEARCH: {"StartSearch", "GetSearchStatus", "GetSearchResults"},
}


def test_services_published(grpc_client):
    published = set(grpc_client.services())
    missing = set(EXPECTED) - published
    assert not missing, f"сервисы не опубликованы: {missing}. Есть: {sorted(published)}"


@pytest.mark.parametrize("service", sorted(EXPECTED))
def test_methods_published(grpc_client, service):
    actual = set(grpc_client.methods(service))
    assert EXPECTED[service] <= actual, f"{service}: нет методов {EXPECTED[service] - actual}"


@pytest.mark.parametrize(("method", "model"), [
    (f"{CATALOG}/GetAuthor", m.Author),
    (f"{CATALOG}/GetBook", m.Book),
    (f"{SEARCH}/GetSearchStatus", m.SearchStatus),
    (f"{SEARCH}/GetSearchResults", m.SearchResults),
])
def test_models_match_service_schema(grpc_client, method, model):
    diff = schema_diff(model, grpc_client.output_message(method))
    assert not any(diff.values()), f"{method}: модель {model.__name__} разошлась со схемой: {diff}"
