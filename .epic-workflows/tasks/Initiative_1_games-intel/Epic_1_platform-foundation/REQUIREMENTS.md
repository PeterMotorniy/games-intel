# Platform Foundation — Requirements

## Functional Requirements

- При старте любого процесса загружается типизированный срез settings; неизвестный ключ — ошибка старта.
- Имена CloudEvents `type`, топиков и consumer groups читаются из `kafka.events.*` / `kafka.consumer_groups.*`, не из Python-констант.
- Каждое исходящее событие имеет `id` (UUIDv7) и детерминированный `idempotencykey` по `idempotency.key_template`.
- Домен и outbox пишутся в одной транзакции; Kafka offset коммитится после COMMIT БД.
- Повтор события с тем же `event_id` или тем же `idempotency_key` — no-op + commit offset.

## Technical Requirements

- Settings: yaml (`APP_CONFIG_PATH`) + overlay `GAMES_INTEL__SECTION__KEY`. Канон ключей: [configuration.md](../../../../docs/architecture/core/configuration.md).
- Контракты: [event-contracts.md](../../../../docs/architecture/events/event-contracts.md) — конверт, payload-модели, DLQ, AsyncAPI из Pydantic (не руками второй раз).
- Схема: [data-model.md](../../../../docs/architecture/database/data-model.md) — все таблицы, unique, `daily_processed_slugs`, `attempt_count`.
- Реплики: [replicas-and-idempotency.md](../../../../docs/architecture/workers/replicas-and-idempotency.md) — INSERT processed_events ON CONFLICT, outbox SKIP LOCKED, advisory lock scheduler.
- Цикл демона: mermaid в [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md) § «Общий цикл демона».
- Исключения: `TransientError`, `NotFoundError`, `ParseError`, `SchemaError`, `QuotaError` — [error-handling.md](../../../../docs/architecture/reliability/error-handling.md).
- Раскладка: `packages/{settings,contracts,db,kafka}`, `infra/compose/` — system-architecture § репозиторий.

## Acceptance Criteria

- [x] Snapshot `config.example.yaml` покрывает канон ключей (тест).
- [x] Тест: все будущие воркеры берут topic из settings (контракт settings-объекта).
- [x] Golden JSON CloudEvents с обязательным `idempotencykey`.
- [x] Миграции применяются на чистой Postgres 16 с `vector` и `pg_trgm`.
- [x] Параллельный insert `processed_events` с одним business key: один успех.
- [x] Outbox + домен rollback вместе.
- [x] Compose поднимает postgres+kafka; init создаёт топики из конфига.
- [x] `enable_auto_commit=false` в клиенте.

## Constraints

- Нет литералов топиков/cron/лимита 20 в коде приложений.
- `os.environ` только в слое settings.
- LangGraph checkpoint таблицы **не** создаёт этот эпик (только Reviews/LetsPlay позже).
- HNSW индекс **не** в миграции 0001 ([similarity.md](../../../../docs/architecture/workers/similarity.md) § индекс).
