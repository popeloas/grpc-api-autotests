"""Шаги теста для отчёта Allure. Без Allure шаг просто пишется в лог."""
from __future__ import annotations

import logging
from contextlib import contextmanager

log = logging.getLogger("autotests.steps")

try:
    import allure

    def step(title: str):
        return allure.step(title)

except ImportError:  # pragma: no cover

    @contextmanager
    def step(title: str):
        log.info("STEP: %s", title)
        yield
