#!/usr/bin/env bash
# Поднять демо-сервис, прогнать тесты, собрать отчёт Allure (если установлен) и остановить сервис.
# Аргументы передаются в pytest: ./tools/run-local.sh -m smoke
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || PY=python3

"$PY" -m demo_service.server --port 50051 --db .demo/library.db > .demo-server.log 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT

for _ in $(seq 1 50); do
  STAND=local "$PY" tools/preflight.py > /dev/null 2>&1 && break
  sleep 0.2
done
STAND=local "$PY" tools/preflight.py

rm -rf allure-results
set +e
STAND=local "$PY" -m pytest -n 4 --alluredir=allure-results "$@"
CODE=$?
set -e

if command -v allure > /dev/null; then
  allure generate allure-results -o allure-report --clean --single-file > /dev/null
  echo "Отчёт: allure-report/index.html"
fi
exit $CODE
