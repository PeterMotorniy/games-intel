# Repositories — Requirements

## Functional Requirements

- Catalog replace `game_platforms` в той же транзакции, что update games catalog-полей.
- Similarity: удалить набор similar для игры (или всех в inline_all) и вставить новый top-K в одной транзакции.
- Ingestion: движение курсора отдельным методом, вызываемым только после успешного listing.
- processed_events: `INSERT … ON CONFLICT DO NOTHING` по event_id **или** idempotency_key, вернуть inserted/duplicate.
- Outbox: insert с unique idempotency_key; claim `FOR UPDATE SKIP LOCKED` where published_at IS NULL AND producer = :worker_type.
- Heartbeats upsert по `(worker_type, instance_id)`.

## Technical Requirements

- [data-model.md](../../../../../../docs/architecture/database/data-model.md) § Репозитории, § транзакция mermaid.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) § БД-замки, § Outbox relay.
- [AGENTS.md](../../../../../../AGENTS.md) § 3: SQL не в сервисах.
- Read-методы для будущего API: list games (q, platform, sort, page), get by slug, platforms distinct, monitor aggregates — можно минимальные, расширит Epic 4/6.

## Acceptance Criteria

- [x] Reviews update не меняет cover_url.
- [x] Conflict idempotency → duplicate flag, без исключения наружу как crash (контролируемый no-op).
- [x] Outbox claim не отдаёт одну строку двум конкурентам.
- [x] Similar replace атомарный: нет окна без строк при ошибке mid-insert (транзакция).
- [x] Discovery-only пишет daily_processed_slugs (метод не в catalog repo).

## Constraints

- Query API не получает write-методы домена игр (кроме outbox tick — отдельный метод).
- Не логировать payload целиком с PII.
