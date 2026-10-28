"""Сверка pydantic-моделей с живой схемой сервиса (через reflection).

Если в ответе метода появилось поле, которого нет в модели, или модель ждёт поле, которого
сервис больше не отдаёт, — тест показывает разницу по именам полей."""
from __future__ import annotations

from pydantic import BaseModel


def schema_diff(model: type[BaseModel], descriptor) -> dict[str, set[str]]:
    service_fields = {f.name for f in descriptor.fields}
    model_fields = set(model.model_fields)
    return {"нет в модели": service_fields - model_fields, "нет в сервисе": model_fields - service_fields}
