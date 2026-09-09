# Idempotent Daemon Loop — Requirements

## Functional Requirements

Порядок в транзакции handler ([replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md)):

1. INSERT processed_events ON CONFLICT DO NOTHING (любой unique).
2. Conflict → commit пустой работы, commit Kafka offset, выход.
3. Иначе работа + upsert домена + outbox с исходящим idempotency_key.
4. Опционально FOR UPDATE на ingestion_items `(run_id, slug, stage)` + lease_seconds.

Retry внутри обработки: offset не commit. attempt_count на item переживает рестарт ([recovery.md](../../../../../../docs/architecture/reliability/recovery.md)).

Heartbeat: status idle/running/error, current_subject, processed_ok/failed (счётчик процесса).

## Technical Requirements

- Цикл mermaid: [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md).
- Матрица commit/DLQ/status: [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md).
- AdapterError → типы воркера: [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) § Ошибка адаптера.
- Retry параметры только `retry.*` settings.
- `kafka.max_poll_interval_ms` > худшего handler.
- source urn из app.name + worker_type.

## Acceptance Criteria

- [x] Два параллельных handler одного события — один persist.
- [x] Новый CloudEvents id, тот же business key — no-op.
- [x] SchemaError: DLQ + commit, домен не меняется.
- [x] Transient × max_attempts: item failed, offset commit.
- [x] Логи JSON с run_id, slug, worker, stage, event_id, error_type, attempt; без HTML/токенов.

## Constraints

- Запрещены `except Exception: pass`.
- Агент/LangGraph в каркас не входит.
- Не ретраить SchemaError, NotFound, стабильный ParseError, Quota.
