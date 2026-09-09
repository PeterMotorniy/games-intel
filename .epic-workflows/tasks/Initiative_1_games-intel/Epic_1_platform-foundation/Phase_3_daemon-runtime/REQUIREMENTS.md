# Daemon Runtime — Requirements

## Functional Requirements

- Consumer не коммитит offset до COMMIT БД (persist + outbox + processed_events) либо до записи DLQ при schema fail (выбрано: commit после успешной записи DLQ).
- SchemaError → DeadLetter `reason=schema`, партиция жива.
- TransientError → backoff, offset не commit, attempt_count++; после max_attempts item failed + optional DLQ + commit.
- Дубль idempotency → commit offset, работы нет.

## Technical Requirements

- Цикл: [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) mermaid.
- Реплики/outbox/keys: [replicas-and-idempotency.md](../../../../../docs/architecture/workers/replicas-and-idempotency.md).
- Классификация: [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) иерархия + retry таблица.
- Якоря: [recovery.md](../../../../../docs/architecture/reliability/recovery.md) § 1, 3, 5.
- Топики и партиции: [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md), [configuration.md](../../../../../docs/architecture/core/configuration.md) `kafka.partitions.*`.
- `source`: `urn:{app.name}:worker:{worker_type}`.
- Исключения в packages: TransientError, NotFoundError, ParseError, SchemaError, QuotaError. Запрет `except Exception: pass`.

## Acceptance Criteria

- [x] enable_auto_commit false.
- [x] Два handler параллельно — один persist.
- [x] Poison message: DLQ, следующее валидное ок.
- [x] Compose postgres+kafka healthy; топики созданы из settings.
- [x] Relay: produce fail оставляет published_at NULL.

## Constraints

- Нет Kafka EOS.
- Нет Redis lock.
- Каркас не зависит от langchain.
