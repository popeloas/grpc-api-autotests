"""Асинхронный поиск: StartSearch → ждём статус DONE → забираем результаты.

Показывает работу с асинхронным API: ожидание через wait_until с понятной ошибкой по таймауту
и негативную проверку «удалённое не появляется» через assert_stays."""
from __future__ import annotations

import uuid

import grpc
import pytest

from autotests.clients.grpc_json import GrpcError
from autotests.data.factories import RUN_ID
from autotests.errors import SearchErrors, assert_grpc_error
from autotests.models import library as m
from autotests.waiting import assert_stays, wait_until

pytestmark = [pytest.mark.writes]


def run_search(search, settings, query: str, genre: m.Genre | None = None) -> m.SearchResults:
    started = search.start(query, genre)
    wait_until(lambda: search.status(str(started.search_id)), lambda s: s.state is m.SearchState.DONE,
               timeout=settings.search_timeout, what=f"поиск «{query}» завершится")
    return search.results(str(started.search_id))


@pytest.mark.smoke
class TestPositive:
    def test_finds_book_by_part_of_title(self, search, settings, book):
        part = book.body["title"].split()[-1]  # уникальный хвост названия
        found = run_search(search, settings, part.upper())  # регистр не важен
        assert [b.id for b in found.books] == [book.model.id]
        assert found.books[0] == book.model

    def test_genre_filter(self, search, settings, seeder, author):
        poem = seeder.book(author, genre="POETRY", title=f"QA Стихи {RUN_ID} {uuid.uuid4().hex[:6]}")
        seeder.book(author, genre="SCIENCE", title=f"QA Физика {RUN_ID} {uuid.uuid4().hex[:6]}")
        found = run_search(search, settings, f"QA Стихи {RUN_ID}", m.Genre.POETRY)
        assert poem.model.id in {b.id for b in found.books}
        assert all(b.genre is m.Genre.POETRY for b in found.books)

    def test_status_in_progress_right_after_start(self, search):
        started = search.start(f"QA {uuid.uuid4().hex}")
        assert search.status(str(started.search_id)).state is m.SearchState.IN_PROGRESS


@pytest.mark.regress
class TestNegative:
    def test_empty_query(self, search):
        with pytest.raises(GrpcError) as err:
            search.start("")
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, SearchErrors.QUERY_REQUIRED)

    def test_unknown_search_id(self, search):
        with pytest.raises(GrpcError) as err:
            search.status(str(uuid.uuid4()))
        assert_grpc_error(err, grpc.StatusCode.NOT_FOUND, SearchErrors.SEARCH_NOT_FOUND)

    def test_results_before_done(self, search):
        started = search.start(f"QA {uuid.uuid4().hex}")
        with pytest.raises(GrpcError) as err:
            search.results(str(started.search_id))
        assert_grpc_error(err, grpc.StatusCode.FAILED_PRECONDITION)

    def test_deleted_book_not_found(self, search, settings, catalog, book):
        title = book.body["title"]
        catalog.delete_book(book.id)
        assert_stays(lambda: run_search(search, settings, title), lambda r: not r.books,
                     duration=settings.search_timeout / 5, what="удалённая книга не находится поиском")


@pytest.mark.regress
@pytest.mark.known_bug
class TestKnownBugs:
    @pytest.mark.xfail(strict=True, reason="БАГ DEMO-3: запрос из пробелов → INTERNAL вместо INVALID_ARGUMENT")
    def test_whitespace_query(self, search):
        with pytest.raises(GrpcError) as err:
            search.start("   ")
        assert_grpc_error(err, grpc.StatusCode.INVALID_ARGUMENT, SearchErrors.QUERY_REQUIRED)
