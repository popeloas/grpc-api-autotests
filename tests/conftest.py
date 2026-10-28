"""Общая подготовка для тестов: стенд, клиенты, тестовые данные, база.

Запуск: STAND=local pytest | pytest -m smoke | pytest -n 4"""
from __future__ import annotations

import os

import pytest

from autotests.clients.grpc_json import GrpcJsonClient
from autotests.clients.library_api import CatalogApi, SearchApi
from autotests.data.seed import CatalogSeeder
from autotests.db.library_db import LibraryDb
from autotests.settings import StandSettings, get_settings

# QA_KEEP_DATA=1 — не удалять тестовые данные после теста (чтобы разобрать падение руками).
# Они уберутся автоматически в начале следующего обычного прогона (по метке qa-autotest).
KEEP_DATA = os.getenv("QA_KEEP_DATA") == "1"


@pytest.fixture(scope="session")
def settings() -> StandSettings:
    return get_settings()


def pytest_report_header(config):
    s = get_settings()
    return [f"stand: {s.stand} | catalog={s.catalog_grpc} | db={'yes' if s.db_file else 'no'} "
            f"| writes={'yes' if s.allow_writes else 'no'}"]


def pytest_collection_modifyitems(config, items):
    """Тесты, которым стенд не подходит, пропускаются с явной причиной — а не падают."""
    s = get_settings()
    rules = {
        "needs_db": (s.db_file is None, "не задан DB_PATH — нет доступа к базе"),
        "writes": (not s.allow_writes, "ALLOW_WRITES=false — стенд только для чтения"),
    }
    for item in items:
        for marker, (skip, reason) in rules.items():
            if skip and marker in item.keywords:
                item.add_marker(pytest.mark.skip(reason=f"стенд {s.stand}: {reason}"))


# --- gRPC ---
@pytest.fixture(scope="session")
def grpc_client(settings) -> GrpcJsonClient:
    client = GrpcJsonClient(settings.catalog_grpc, timeout=settings.grpc_timeout)
    yield client
    client.close()


@pytest.fixture(scope="session")
def catalog(grpc_client) -> CatalogApi:
    return CatalogApi(grpc_client)


@pytest.fixture(scope="session")
def search(grpc_client) -> SearchApi:
    return SearchApi(grpc_client)


# --- БД ---
@pytest.fixture(scope="session")
def db(settings) -> LibraryDb:
    if settings.db_file is None:
        pytest.skip("DB_PATH не задан")
    conn = LibraryDb(settings.db_file)
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_qa_leftovers(settings, catalog):
    """Перед прогоном убираем остатки прошлых упавших прогонов — только записи с меткой qa-autotest.
    Удаление идёт через API сервиса, в базу тесты не пишут."""
    # При запуске в несколько потоков (pytest -n) убираем только в первом, иначе поток, стартовавший
    # позже, удалит данные тестов, которые уже идут в других.
    if os.getenv("PYTEST_XDIST_WORKER", "gw0") != "gw0" or not (settings.db_file and settings.allow_writes):
        yield
        return
    if settings.db_file.exists():
        conn = LibraryDb(settings.db_file)
        left = conn.qa_leftovers()
        conn.close()
        seeder = CatalogSeeder(catalog)
        for book_id in left["books"]:
            seeder.track_book(book_id)
        for author_id in left["authors"]:
            seeder.track_author(author_id)
        problems = seeder.cleanup()
        if any(left.values()):
            print(f"\n[cleanup] удалены остатки прошлых прогонов: {len(left['books'])} книг, "
                  f"{len(left['authors'])} авторов {problems or ''}")
    yield


# --- тестовые данные ---
@pytest.fixture
def seeder(catalog):
    """Создаёт данные и гарантированно удаляет их после теста."""
    s = CatalogSeeder(catalog)
    yield s
    if KEEP_DATA:
        print(f"\n[QA_KEEP_DATA] оставлено: books={s._books} authors={s._authors}")
        return
    problems = s.cleanup()
    assert not problems, f"не удалось вычистить тестовые данные: {problems}"


@pytest.fixture
def author(seeder):
    return seeder.author()


@pytest.fixture
def book(seeder, author):
    return seeder.book(author)
