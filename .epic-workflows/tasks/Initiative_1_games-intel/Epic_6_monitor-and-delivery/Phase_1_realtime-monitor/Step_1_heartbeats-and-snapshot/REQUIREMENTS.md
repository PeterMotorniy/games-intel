# Heartbeats and Snapshot — Requirements

## Functional Requirements

- Upsert heartbeat: worker_type, instance_id, status idle|running|error, current_subject, processed_ok, processed_failed, lag_hint, observed_at.
- GET /monitor: workers (все instance), runs сегодня, counts по stage×status, cursor new_releases_done/last_browse_page/process_date, scrape.* .
- parse_error count за сутки из ingestion_items.error_type.
- processed_ok в строке воркера — счётчик процесса; глобальные — items.

## Technical Requirements

- [data-model.md](../../../../../../docs/architecture/database/data-model.md) worker_heartbeats, adapter_health.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) WorkerHeartbeat (если публикуется в Kafka — consume sink; канон UI читает БД).
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) § Heartbeat.
- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) GET /monitor.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) поля scrape.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) heartbeat_interval_seconds, monitor.heartbeat_stale_seconds.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) запись ошибки items.

## Acceptance Criteria

- [x] Две instance catalog в ответе.
- [x] circuit_state из adapter_health.
- [x] Counts failed/degraded раздельно.
- [x] Нет секретов в JSON.

## Constraints

- Не алертить в API каждый degraded.
- Не отдавать payload DLQ целиком в монитор MVP (достаточно counts / circuit).
