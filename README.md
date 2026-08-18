# Асинхронный сервис процессинга платежей

Принимает запросы на оплату, обрабатывает их через эмуляцию платёжного шлюза и уведомляет клиента вебхуком.

API создаёт платёж в статусе pending и в той же транзакции пишет событие в таблицу outbox. Отдельный процесс публикует накопившиеся события в RabbitMQ, consumer читает очередь payments.new, проводит платёж через шлюз, обновляет статус и отправляет вебхук. Сообщения, которые не удалось обработать, уходят в DLQ.

Стек: FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), PostgreSQL, RabbitMQ (FastStream), Alembic, Docker.

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы: postgres, rabbitmq, migrations, api, outbox, consumer.

- API: http://localhost:8000, Swagger: http://localhost:8000/docs
- RabbitMQ: http://localhost:15672 (guest / guest)

```bash
make logs     # логи consumer и outbox
make check    # ruff + mypy + pytest
make down     # остановить, удалить тома
```

## API

Все эндпоинты требуют заголовок X-API-Key, кроме /health.

Создание платежа, заголовок Idempotency-Key обязателен:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: local-api-key' \
  -H 'Idempotency-Key: order-1001' \
  -H 'Content-Type: application/json' \
  -d '{"amount": "1500.00", "currency": "RUB", "description": "Оплата заказа 1001",
       "metadata": {"order_id": 1001}, "webhook_url": "https://webhook.site/your-uuid"}'
```

```json
{"payment_id": "f7f06155-a400-4f28-87d8-e6328772b6d2", "status": "pending",
 "created_at": "2026-08-18T10:12:41.318204Z"}
```

Ответ 202. Повторный запрос с тем же Idempotency-Key вернёт уже созданный платёж.

Получение платежа:

```bash
curl http://localhost:8000/api/v1/payments/f7f06155-a400-4f28-87d8-e6328772b6d2 \
  -H 'X-API-Key: local-api-key'
```

```json
{"payment_id": "f7f06155-a400-4f28-87d8-e6328772b6d2", "amount": "1500.00", "currency": "RUB",
 "description": "Оплата заказа 1001", "metadata": {"order_id": 1001}, "status": "succeeded",
 "idempotency_key": "order-1001", "webhook_url": "https://webhook.site/your-uuid",
 "created_at": "2026-08-18T10:12:41.318204Z", "processed_at": "2026-08-18T10:12:45.204871Z"}
```

Коды: 202 принят, 200 найден, 404 не найден, 401 неверный ключ, 403 нет заголовка X-API-Key, 422 невалидное тело или нет Idempotency-Key.

После обработки consumer шлёт на webhook_url:

```json
{"payment_id": "f7f06155-a400-4f28-87d8-e6328772b6d2", "status": "succeeded", "amount": "1500.00",
 "currency": "RUB", "description": "Оплата заказа 1001", "metadata": {"order_id": 1001},
 "processed_at": "2026-08-18T10:12:45.204871+00:00"}
```

Схема очереди в AsyncAPI:

```bash
docker compose exec consumer faststream docs gen cli.consumer:app --out /tmp/asyncapi.json
```

## Структура

- src/payments/domain - агрегат Payment, Money, доменные события
- src/payments/application - use cases и интерфейсы: репозитории, UoW, шлюз, webhook, publisher
- src/payments/infrastructure - SQLAlchemy, RabbitMQ, HTTP-клиент, эмуляция шлюза
- src/payments/presentation - HTTP-роутеры и подписчики RabbitMQ
- src/bootstrap - конфигурация и сборка зависимостей
- cli - точки входа: api, consumer, outbox

Зависимости направлены к домену: домен не знает про БД и брокер, use cases работают с интерфейсами, реализации подставляются в bootstrap/containers.py.

## Как обеспечены гарантии

**Outbox.** Платёж и событие пишутся одной транзакцией, публикует их отдельный процесс. Если брокер недоступен, событие останется в таблице и уедет позже. Доставка at-least-once: дубль возможен, если публикация прошла, а published_at не закоммитился.

**Идемпотентность.** Уникальный индекс по idempotency_key; при гонке запросов ловим IntegrityError и возвращаем существующий платёж. Consumer не обрабатывает платёж, который уже не в статусе pending, и не перезаписывает чужой результат: UPDATE ... WHERE status = 'pending'.

**Retry и DLQ.** Вебхук отправляется до трёх раз с задержками 1, 2, 4 секунды. После последней неудачи исключение доходит до брокера, подписчик работает с ack_policy=REJECT_ON_ERROR, и сообщение уходит в payments.new.dlq через payments.dlx.

```bash
docker compose exec rabbitmq rabbitmqctl list_queues name messages
```

**Индексы.** uq_payments_idempotency_key защищает от дублей. ix_outbox_unpublished частичный, (occurred_at) WHERE published_at IS NULL, покрывает запрос релея и не растёт вместе с историей отправленных событий.

## Конфигурация

Все настройки в переменных окружения, вложенные разделяются двойным подчёркиванием: DB__HOST, RABBIT__PORT. Полный список с дефолтами в .env.example: доступы к БД и брокеру, API_KEY, параметры эмуляции шлюза, число попыток вебхука, размер пачки outbox, prefetch_count консьюмера.

## Тесты

```bash
make test
```

19 юнит-тестов на домен и сценарии, инфраструктура заменена заглушками из tests/fakes.py, БД и брокер не нужны.

## Ограничения

- релей опрашивает таблицу раз в секунду, для больших объёмов нужен LISTEN/NOTIFY или CDC;
- отправленные события из outbox не удаляются, нужна архивация;
- сообщения в DLQ разбираются вручную;
- нет circuit breaker на вебхуки и шлюз.

## Локальная разработка

Нужны поднятые postgres и rabbitmq, в .env указать DB__HOST=localhost.

```bash
poetry install
PYTHONPATH=src poetry run alembic upgrade head
PYTHONPATH=src poetry run uvicorn cli.api:app --reload
PYTHONPATH=src poetry run python -m cli.outbox
PYTHONPATH=src poetry run python -m cli.consumer
```
