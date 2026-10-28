"""Ожидание результата, который появляется не сразу (асинхронный поиск, фоновые задачи)."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def wait_until(fetch: Callable[[], T], done: Callable[[T], bool], *, timeout: float = 15.0,
               interval: float = 0.3, what: str = "условие") -> T:
    """Опрашивает fetch, пока done(значение) не станет True. По таймауту — понятная ошибка
    с последним полученным значением."""
    deadline = time.monotonic() + timeout
    last: T = fetch()
    while not done(last):
        if time.monotonic() >= deadline:
            raise AssertionError(f"Не дождались: {what} за {timeout:.0f} с. Последнее значение: {last!r}")
        time.sleep(interval)
        last = fetch()
    return last


def assert_stays(fetch: Callable[[], T], ok: Callable[[T], bool], *, duration: float = 3.0,
                 interval: float = 0.3, what: str = "условие") -> T:
    """Негативная проверка асинхронного пути: условие держится всё время duration
    (например, «удалённая книга так и не появилась в поиске»)."""
    deadline = time.monotonic() + duration
    while True:
        last = fetch()
        if not ok(last):
            raise AssertionError(f"Нарушено: {what}. Значение: {last!r}")
        if time.monotonic() >= deadline:
            return last
        time.sleep(interval)
