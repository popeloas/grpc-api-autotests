"""Ожидаемые тексты ошибок сервиса и проверка ошибки.

Код ошибки проверяется всегда, текст — по части строки: формулировки меняют чаще, чем коды."""
from __future__ import annotations

import grpc
import pytest

from autotests.clients.grpc_json import GrpcError


class CatalogErrors:
    NAME_REQUIRED = "name is required"
    TITLE_REQUIRED = "title is required"
    BIRTH_YEAR_OUT_OF_RANGE = "birth_year out of range"
    INVALID_AUTHOR_ID = "invalid author id"
    INVALID_BOOK_ID = "invalid book id"
    AUTHOR_NOT_FOUND = "author not found"
    BOOK_NOT_FOUND = "book not found"
    AUTHOR_HAS_BOOKS = "author has books"


class SearchErrors:
    QUERY_REQUIRED = "query is required"
    SEARCH_NOT_FOUND = "search not found"


def assert_grpc_error(err: pytest.ExceptionInfo[GrpcError] | GrpcError, code: grpc.StatusCode,
                      contains: str | None = None) -> None:
    e = err.value if isinstance(err, pytest.ExceptionInfo) else err
    assert e.code == code, f"{e.method}: ожидался код {code.name}, получен {e.code.name} ({e.details})"
    if contains is not None:
        assert contains in e.details, f"{e.method}: в тексте ошибки нет «{contains}»: «{e.details}»"
