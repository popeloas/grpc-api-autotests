"""Демо gRPC-сервис «Каталог библиотеки» — стенд, на котором работают автотесты.

Запуск: python -m demo_service.server [--port 50051] [--db .demo/library.db]

Включён server reflection: клиенты (grpcurl, Postman, автотесты) берут описание методов у сервиса,
.proto им не нужны.

В сервисе НАРОЧНО оставлены три ошибки — они помечены «DEMO BUG» и описаны в README.
Автотесты ведут их в группе известных багов."""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
import uuid
from concurrent import futures
from datetime import date
from pathlib import Path

import grpc
from grpc_reflection.v1alpha import reflection

HERE = Path(__file__).resolve().parent
GEN = HERE / "gen"


def _ensure_generated() -> None:
    """Код из .proto генерируется при первом запуске (grpcio-tools)."""
    target = GEN / "library" / "v1" / "library_pb2.py"
    proto = HERE / "proto" / "library" / "v1" / "library.proto"
    if target.exists() and target.stat().st_mtime >= proto.stat().st_mtime:
        return
    from grpc_tools import protoc

    GEN.mkdir(exist_ok=True)
    code = protoc.main([
        "grpc_tools.protoc", f"-I{HERE / 'proto'}", f"--python_out={GEN}", f"--grpc_python_out={GEN}",
        "library/v1/library.proto",
    ])
    if code != 0:
        raise RuntimeError("не удалось сгенерировать код из library.proto")


_ensure_generated()
sys.path.insert(0, str(GEN))

from library.v1 import library_pb2 as pb  # noqa: E402
from library.v1 import library_pb2_grpc as pb_grpc  # noqa: E402

from demo_service.storage import Storage  # noqa: E402

log = logging.getLogger("demo_service")

SEARCH_DELAY_SEC = float(os.getenv("DEMO_SEARCH_DELAY", "1.0"))


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _author_msg(row) -> pb.Author:
    return pb.Author(id=row["id"], name=row["name"], country=row["country"], birth_year=row["birth_year"],
                     tag=row["tag"])


def _book_msg(row) -> pb.Book:
    return pb.Book(
        id=row["id"], author_id=row["author_id"], title=row["title"], genre=row["genre"], year=row["year"],
        price=pb.Price(amount=row["price_amount"], discounted_amount=row["price_discounted"],
                       currency=row["price_currency"]),
        available=bool(row["available"]), tag=row["tag"],
    )


class CatalogService(pb_grpc.CatalogServiceServicer):
    def __init__(self, db: Storage):
        self.db = db

    # --- авторы ---
    def CreateAuthor(self, request, context):
        if not request.name.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")
        if not 0 <= request.birth_year <= date.today().year:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"birth_year out of range: {request.birth_year}")
        author_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO authors (id, name, country, birth_year, tag) VALUES (?, ?, ?, ?, ?)",
            (author_id, request.name.strip(), request.country, request.birth_year, request.tag),
        )
        return _author_msg(self.db.one("SELECT * FROM authors WHERE id = ?", (author_id,)))

    def GetAuthor(self, request, context):
        if not _valid_uuid(request.id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid author id: {request.id!r}")
        row = self.db.one("SELECT * FROM authors WHERE id = ?", (request.id,))
        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "author not found")
        return _author_msg(row)

    def DeleteAuthor(self, request, context):
        if not _valid_uuid(request.id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid author id: {request.id!r}")
        if self.db.one("SELECT 1 FROM books WHERE author_id = ?", (request.id,)):
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "author has books")
        if self.db.execute("DELETE FROM authors WHERE id = ?", (request.id,)).rowcount == 0:
            context.abort(grpc.StatusCode.NOT_FOUND, "author not found")
        return pb.DeleteResponse()

    # --- книги ---
    def UpsertBook(self, request, context):
        if request.id and not _valid_uuid(request.id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid book id: {request.id!r}")
        if not request.title.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "title is required")
        if not _valid_uuid(request.author_id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid author id: {request.author_id!r}")
        if not self.db.one("SELECT 1 FROM authors WHERE id = ?", (request.author_id,)):
            context.abort(grpc.StatusCode.NOT_FOUND, "author not found")
        if request.price.amount < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "price.amount must be >= 0")
        # DEMO BUG 1: нет проверки «цена со скидкой не больше цены» —
        # сервис сохраняет discounted_amount > amount.
        book_id = request.id or str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO books (id, author_id, title, genre, year, price_amount, price_discounted,
                                  price_currency, available, tag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET author_id=excluded.author_id, title=excluded.title,
                 genre=excluded.genre, year=excluded.year, price_amount=excluded.price_amount,
                 price_discounted=excluded.price_discounted, price_currency=excluded.price_currency,
                 available=excluded.available, tag=excluded.tag""",
            (book_id, request.author_id, request.title.strip(), request.genre, request.year, request.price.amount,
             request.price.discounted_amount, request.price.currency, int(request.available), request.tag),
        )
        return _book_msg(self.db.one("SELECT * FROM books WHERE id = ?", (book_id,)))

    def GetBook(self, request, context):
        # DEMO BUG 2: пустой id не проверяется — uuid.UUID('') падает внутри, клиент получает
        # INTERNAL вместо INVALID_ARGUMENT.
        try:
            uuid.UUID(request.id)
        except ValueError:
            if request.id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid book id: {request.id!r}")
            context.abort(grpc.StatusCode.INTERNAL, "internal error")
        row = self.db.one("SELECT * FROM books WHERE id = ?", (request.id,))
        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "book not found")
        return _book_msg(row)

    def DeleteBook(self, request, context):
        if not _valid_uuid(request.id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid book id: {request.id!r}")
        if self.db.execute("DELETE FROM books WHERE id = ?", (request.id,)).rowcount == 0:
            context.abort(grpc.StatusCode.NOT_FOUND, "book not found")
        return pb.DeleteResponse()

    def ListBooksByAuthor(self, request, context):
        if not _valid_uuid(request.author_id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"invalid author id: {request.author_id!r}")
        for row in self.db.all("SELECT * FROM books WHERE author_id = ? ORDER BY title", (request.author_id,)):
            yield _book_msg(row)


class SearchService(pb_grpc.SearchServiceServicer):
    """Поиск выполняется в фоне и готов через DEMO_SEARCH_DELAY секунд — как настоящий асинхронный поиск."""

    def __init__(self, db: Storage):
        self.db = db
        self._searches: dict[str, dict] = {}
        self._lock = threading.Lock()

    def StartSearch(self, request, context):
        # DEMO BUG 3: проверка на пустой запрос сделана до обрезки пробелов — запрос из пробелов
        # проходит дальше и падает: INTERNAL вместо INVALID_ARGUMENT.
        if request.query == "":
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query is required")
        if not request.query.strip():
            context.abort(grpc.StatusCode.INTERNAL, "internal error")
        search_id = str(uuid.uuid4())
        with self._lock:
            self._searches[search_id] = {"state": pb.IN_PROGRESS, "books": []}
        threading.Thread(target=self._run, args=(search_id, request.query.strip(), request.genre),
                         daemon=True).start()
        return pb.StartSearchResponse(search_id=search_id)

    def _run(self, search_id: str, query: str, genre: int) -> None:
        time.sleep(SEARCH_DELAY_SEC)
        # Регистр сравниваем в Python: lower() в SQLite не понимает кириллицу.
        sql, params = ("SELECT * FROM books WHERE genre = ? ORDER BY title", (genre,)) if genre else \
            ("SELECT * FROM books ORDER BY title", ())
        needle = query.casefold()
        books = [_book_msg(r) for r in self.db.all(sql, params) if needle in r["title"].casefold()]
        with self._lock:
            self._searches[search_id] = {"state": pb.DONE, "books": books}

    def _get(self, search_id: str, context) -> dict:
        with self._lock:
            search = self._searches.get(search_id)
        if search is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "search not found")
        return search

    def GetSearchStatus(self, request, context):
        return pb.SearchStatus(search_id=request.search_id, state=self._get(request.search_id, context)["state"])

    def GetSearchResults(self, request, context):
        search = self._get(request.search_id, context)
        if search["state"] != pb.DONE:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "search is still in progress")
        return pb.SearchResults(search_id=request.search_id, books=search["books"])


def serve(port: int, db_path: str) -> grpc.Server:
    db = Storage(db_path)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    pb_grpc.add_CatalogServiceServicer_to_server(CatalogService(db), server)
    pb_grpc.add_SearchServiceServicer_to_server(SearchService(db), server)
    names = (
        pb.DESCRIPTOR.services_by_name["CatalogService"].full_name,
        pb.DESCRIPTOR.services_by_name["SearchService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(names, server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    log.info("demo service on :%s, db=%s", port, db_path)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Демо gRPC-сервис «Каталог библиотеки»")
    parser.add_argument("--port", type=int, default=int(os.getenv("DEMO_PORT", "50051")))
    parser.add_argument("--db", default=os.getenv("DEMO_DB_PATH", ".demo/library.db"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    serve(args.port, args.db).wait_for_termination()


if __name__ == "__main__":
    main()
