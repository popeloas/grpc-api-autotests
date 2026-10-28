# gRPC API autotests · pytest + pydantic

[![autotests](https://github.com/popeloas/grpc-api-autotests/actions/workflows/autotests.yml/badge.svg)](https://github.com/popeloas/grpc-api-autotests/actions/workflows/autotests.yml)

Шаблон автотестов для gRPC-микросервисов. Сюда вынесен подход, который я использую в работе
с бэкенд-сервисами, а вместо реальных сервисов — небольшой демо-сервис «Каталог библиотеки»,
чтобы всё можно было запустить за минуту.

*A template for testing gRPC microservices with pytest and pydantic: reflection-based client (no .proto
needed in tests), self-cleaning test data, request → response → DB checks, async scenarios, contract drift
detection, known bugs tracked with strict xfail, Allure reports and CI on GitHub Actions.*

## Что здесь показано

| Приём | Зачем | Где |
|---|---|---|
| **gRPC-клиент через server reflection** | тестам не нужны .proto и сгенерированный код — методы берутся у сервиса, как в Postman | `src/autotests/clients/grpc_json.py` |
| **Ответы — через pydantic-модели** (`extra="forbid"`) | сервис добавил или переименовал поле — тест сразу показывает какое | `src/autotests/models/` |
| **Контрактные тесты** | опубликованы ли все методы и совпадают ли модели тестов со схемой сервиса | `tests/contract/` |
| **Тестовые данные с автоуборкой** | тест создаёт только свои данные (метка `qa-autotest`) и удаляет их; остатки упавших прогонов убираются перед следующим | `src/autotests/data/seed.py`, `tests/conftest.py` |
| **Сверка «запрос → ответ → база»** | проверяется не только ответ, но и что реально легло в БД; при расхождении — список всех несовпавших полей | `src/autotests/assertions.py` |
| **Асинхронные сценарии** | `wait_until` — ждём результат с понятной ошибкой по таймауту; `assert_stays` — «удалённое так и не появилось» | `src/autotests/waiting.py`, `tests/search/` |
| **Server-streaming** | поток ответов проверяется как список моделей | `test_list_books_by_author_stream` |
| **Известные баги** | тест описывает правильное поведение и помечен `xfail(strict=True)`: баг исправят — тест упадёт с XPASS и напомнит перенести его в обычную группу | классы `TestKnownBugs` |
| **Стенды** | один набор тестов на любом стенде; что стенду недоступно (база, запись) — пропускается с причиной, а не падает | `stands/`, `settings.py` |
| **Preflight** | перед прогоном проверяет, что стенд жив, — вместо сотни одинаково красных тестов | `tools/preflight.py` |
| **Метки smoke / regress** | smoke — на каждый деплой, regress — по расписанию; линтер не пропустит тест без метки | `tools/check_markers.py` |
| **Allure и CI** | шаги в отчёте, прогон на каждый push и каждое утро, отчёт — артефактом | `.github/workflows/autotests.yml` |

## Быстрый старт

Нужен Python 3.11+.

```bash
make setup          # окружение и зависимости
./tools/run-local.sh  # поднять демо-сервис, прогнать тесты, остановить сервис
```

Результат:

```
39 passed, 3 xfailed in 6.5s
XFAIL TestKnownBugs::test_discount_above_price_rejected - БАГ DEMO-1: сервис сохраняет цену со скидкой больше цены
XFAIL TestKnownBugs::test_get_book_empty_id - БАГ DEMO-2: GetBook с пустым id → INTERNAL вместо INVALID_ARGUMENT
XFAIL TestKnownBugs::test_whitespace_query - БАГ DEMO-3: запрос из пробелов → INTERNAL вместо INVALID_ARGUMENT
```

Пошагово, с сервисом в отдельном окне:

```bash
make demo           # окно 1: демо-сервис на localhost:50051
make preflight      # окно 2: стенд доступен?
make test           # все тесты в 4 потока
make smoke          # быстрый набор
make known-bugs     # только известные баги
make report         # отчёт Allure (нужен allure CLI)
```

`QA_KEEP_DATA=1 make test` — не удалять тестовые данные после прогона, чтобы разобрать падение руками.
В начале следующего обычного прогона они уберутся сами.

## Демо-сервис

`demo_service/` — gRPC-сервис на Python (SQLite, reflection включён):

- `library.v1.CatalogService` — авторы и книги: создание, чтение, upsert, удаление, поток книг автора;
- `library.v1.SearchService` — асинхронный поиск: `StartSearch` → `GetSearchStatus` (ждём `DONE`) → `GetSearchResults`.

Посмотреть руками: `grpcurl -plaintext localhost:50051 list`.

### Известные баги (оставлены специально)

| | Что не так | Тест |
|---|---|---|
| DEMO-1 | `UpsertBook` сохраняет цену со скидкой больше обычной цены | `test_discount_above_price_rejected` |
| DEMO-2 | `GetBook` с пустым id → `INTERNAL` вместо `INVALID_ARGUMENT` | `test_get_book_empty_id` |
| DEMO-3 | `StartSearch` с запросом из пробелов → `INTERNAL` вместо `INVALID_ARGUMENT` | `test_whitespace_query` |

Попробуйте исправить любой из них в `demo_service/server.py` (места помечены `DEMO BUG`) — соответствующий
тест упадёт с `XPASS(strict)`: так тесты сообщают, что баг починен и проверку пора перевести в обычную группу.

## Структура

```
demo_service/            демо gRPC-сервис (стенд для тестов)
src/autotests/
  clients/grpc_json.py   gRPC через reflection: dict → запрос, ответ → dict
  clients/library_api.py типизированные вызовы, каждый — шаг в Allure
  models/                pydantic-модели ответов
  data/                  фабрики данных (Faker) и сидер с уборкой
  db/                    чтение базы для сверки (только чтение)
  assertions.py          сравнение запрос / ответ / база
  errors.py              ожидаемые коды и тексты ошибок
  waiting.py             wait_until, assert_stays
  settings.py            стенды: stands/<стенд>.env (+ .secrets.env вне git)
tests/
  contract/              опубликованные методы, модели vs схема
  catalog/               авторы и книги: позитивные, негативные, бизнес-правила, известные баги
  search/                асинхронный поиск
tools/                   preflight, проверка меток, запуск «сервис + тесты»
```

Каждый файл тестов устроен одинаково: `TestPositive` → `TestNegative` → `TestBusinessRules` → `TestKnownBugs`.

## Как добавить свой сервис

1. Адрес — в `stands/<стенд>.env`, секреты — в `stands/<стенд>.secrets.env` (в git не попадает).
2. Модели ответов — в `src/autotests/models/`, обёртку методов — в `src/autotests/clients/`.
3. Создание и удаление данных — в сидер; тесты получают данные через фикстуры и не думают об уборке.
4. Тесты — по шаблону классов выше, у каждого метка `smoke` или `regress`.

---

Автор: **Антон Попело**, QA Engineer · backend / API / gRPC
