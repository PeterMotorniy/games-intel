# Kafka and Outbox — Requirements

## Functional Requirements

- Собрать CloudEvent: id UUIDv7, type/topic из settings, idempotencykey по шаблону, time RFC3339 UTC.
- Relay: `WHERE published_at IS NULL AND producer = :worker_type FOR UPDATE SKIP LOCKED`; после produce — published_at.
- Повтор produce с тем же CloudEvents `id` безопасен для consumers.
- Топик DLQ из `kafka.events.dlq`.

## Technical Requirements

- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) конверт, партиционирование.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) § Outbox relay: producer = worker_type не instance.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) § 3.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) таблица outbox.
- Конфиг: bootstrap, security, max_poll_records, session_timeout, retention, replication_factor — [configuration.md](../../../../../../docs/architecture/core/configuration.md).
- `enable_auto_commit=false`.

## Acceptance Criteria

- [x] Unique outbox.idempotency_key не даёт две копии исходящего события.
- [x] Produce fail → строка unpublished, цикл повторит.
- [x] Kafka key = partition_key (slug или run_id).
- [x] topic_prefix применяется если задан.

## Constraints

- Не commit consumer offset в этом шаге без связки с БД (следующий шаг).
- Не использовать instance_id как producer outbox.
