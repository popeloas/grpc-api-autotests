"""Настройки стенда.

Стенд выбирается переменной STAND (local по умолчанию). Значения — из stands/<стенд>.env
и stands/<стенд>.secrets.env (пароли и ключи, в git не попадает)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STANDS_DIR = PROJECT_ROOT / "stands"


class StandSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file_encoding="utf-8")

    stand: str = "local"

    # gRPC-адрес сервиса (host:port)
    catalog_grpc: str = "localhost:50051"
    grpc_timeout: float = 10.0

    # Можно ли создавать и удалять тестовые данные. На общем стенде с чужими данными — false.
    allow_writes: bool = True

    # Путь к файлу базы сервиса — для проверок «что легло в БД». Не задан — тесты needs_db пропускаются.
    db_path: str | None = None

    # Сколько ждать асинхронный поиск
    search_timeout: float = 15.0

    @property
    def db_file(self) -> Path | None:
        if not self.db_path:
            return None
        p = Path(self.db_path)
        return p if p.is_absolute() else PROJECT_ROOT / p


@lru_cache
def get_settings() -> StandSettings:
    stand = os.getenv("STAND", "local")
    files = [STANDS_DIR / f"{stand}.env", STANDS_DIR / f"{stand}.secrets.env"]
    existing = [str(f) for f in files if f.exists()]
    if not existing:
        raise RuntimeError(f"Нет конфигурации стенда '{stand}': ожидается {files[0]}")
    return StandSettings(_env_file=existing, stand=stand)
