# Monitor and Delivery — Requirements

## Functional Requirements

- Таблица воркеров: `worker_type`, `instance_id`, status, current_subject, counters, last seen; stale по `monitor.heartbeat_stale_seconds`.
- Счётчики: runs сегодня; discovered/cataloged/reviews/letsplay/similar по status включая failed/degraded.
- Курсор: `new_releases_done`, `last_browse_page`, `process_date`.
- Скрейпинг: `circuit_state`, `last_parse_error_at`, count parse_error за сутки. Circuit open — явный статус.
- Кнопка «Запустить сейчас»: disabled in-flight; toast 202; `run_accepted`. При стоящем курсоре — replay той же страницы listing.
- Стенд Compose поднимается одной командой из README; health/ready: Postgres + Kafka; sidecar `/healthz`.

## Technical Requirements

- API: `GET /monitor`, `GET /monitor/stream`, `POST /runs` — [web-ui.md](../../../../docs/architecture/frontend/web-ui.md).
- Heartbeat PK `(worker_type, instance_id)` — [data-model.md](../../../../docs/architecture/database/data-model.md), [replicas-and-idempotency.md](../../../../docs/architecture/workers/replicas-and-idempotency.md).
- POST пишет CloudEvent `kafka.events.schedule_tick` в outbox API (`trigger=manual`, `process_date` из timezone settings). UI не знает имён воркеров.
- SSE читает БД, не Kafka. `aria-live` с debounce. Не кэшировать `/monitor`.
- Матрица ошибок и тесты: [error-handling.md](../../../../docs/architecture/reliability/error-handling.md) § Testing Strategy.
- Recovery тесты: [recovery.md](../../../../docs/architecture/reliability/recovery.md) § Testing Strategy.
- Deployment: system-architecture § Deployment Considerations; `kafka.partitions.game_events >=` реплик стадий игр.
- Конфиг `api.*`, `web.*`, `monitor.*`, `scheduler.tick_source` — [configuration.md](../../../../docs/architecture/core/configuration.md).

## Acceptance Criteria

- [ ] Две реплики Catalog видны двумя строками; stale подсвечен.
- [ ] SSE обновляет статусы без перезагрузки.
- [ ] POST `/runs` не ждёт воркеров; появляется tick/run.
- [ ] Poison CloudEvent → DLQ + следующее валидное обрабатывается.
- [ ] parse_error не двигает курсор; listing 500 × N → run failed.
- [ ] Kill после persist до offset → no duplicate domain; unpublished outbox догоняется.
- [ ] attempt_count не сбрасывается рестартом процесса.
- [ ] Compose replicas: общий consumer group, разный instance_id (`HOSTNAME`).
- [ ] README: как поднять стенд, какие env, куда смотреть UI.

## Constraints

- Не показывать секреты, промпты, сырые транскрипты.
- Не алертить каждый `degraded` летсплея.
- Не публиковать Kafka наружу для браузера.
- Сдача: репозиторий + URL сервиса + JSONL переписки — по [task.md](../../../../task.md); сами JSONL не коммитить как секрет.
