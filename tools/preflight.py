"""Проверка стенда перед прогоном: сервис отвечает, reflection включён, база доступна.

Запуск: STAND=local python tools/preflight.py. Если что-то не так — понятное сообщение и код 1,
вместо сотни одинаково красных тестов."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import grpc  # noqa: E402

from autotests.clients.grpc_json import GrpcJsonClient  # noqa: E402
from autotests.settings import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    ok = True
    print(f"стенд: {s.stand}")
    try:
        grpc.channel_ready_future(grpc.insecure_channel(s.catalog_grpc)).result(timeout=5)
        services = GrpcJsonClient(s.catalog_grpc).services()
        print(f"  [ok] {s.catalog_grpc}: {', '.join(x for x in services if 'reflection' not in x)}")
    except grpc.FutureTimeoutError:
        print(f"  [!!] {s.catalog_grpc}: не отвечает за 5 с — сервис запущен? (make demo)")
        ok = False
    except Exception as e:  # noqa: BLE001
        print(f"  [!!] {s.catalog_grpc}: reflection недоступен — {e}")
        ok = False
    if s.db_file is None:
        print("  [--] база: DB_PATH не задан, тесты needs_db будут пропущены")
    elif s.db_file.exists():
        print(f"  [ok] база: {s.db_file}")
    else:
        print(f"  [!!] база: файла {s.db_file} нет")
        ok = False
    print(f"  [{'ok' if s.allow_writes else '--'}] запись тестовых данных: {'да' if s.allow_writes else 'нет'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
