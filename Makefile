PY ?= .venv/bin/python

.PHONY: setup demo preflight test smoke known-bugs report lint check-markers ci

setup:            ## виртуальное окружение и зависимости
	python3 -m venv .venv
	$(PY) -m pip install -q -U pip
	$(PY) -m pip install -q -e ".[dev]"

demo:             ## запустить демо-сервис (в отдельном окне)
	$(PY) -m demo_service.server --port 50051 --db .demo/library.db

preflight:        ## проверить, что стенд доступен
	STAND=$${STAND:-local} $(PY) tools/preflight.py

test:             ## все тесты в 4 потока (сервис должен быть запущен)
	STAND=$${STAND:-local} $(PY) -m pytest -n 4 --alluredir=allure-results

smoke:            ## быстрый набор
	STAND=$${STAND:-local} $(PY) -m pytest -m smoke

known-bugs:       ## только известные баги
	STAND=$${STAND:-local} $(PY) -m pytest -m known_bug -v

report:           ## открыть отчёт Allure (нужен allure CLI)
	allure serve allure-results

lint:
	$(PY) -m ruff check src tests tools demo_service

check-markers:
	$(PY) tools/check_markers.py tests

ci: lint check-markers  ## всё, что делает CI: сервис + тесты + отчёт
	./tools/run-local.sh
