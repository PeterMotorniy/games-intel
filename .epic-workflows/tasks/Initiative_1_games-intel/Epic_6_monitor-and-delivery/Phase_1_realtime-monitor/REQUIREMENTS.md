# Realtime Monitor Phase — Requirements

## Functional Requirements

- Снимок: workers[], run суток, counts stage/status, cursor, scrape circuit/last_parse_error/parse_error count.
- SSE тех же кадров.
- POST /runs → 202 run_accepted; CloudEvent schedule_tick trigger=manual; process_date из timezone.
- UI таблица реплик, stale, кнопка disabled in-flight, toast, aria-live debounce.
- Circuit open заметный. Не секреты/промпты/транскрипты.

## Technical Requirements

- [web-ui.md](../../../../../docs/architecture/frontend/web-ui.md) монитор, API table, SSE.
- [replicas-and-idempotency.md](../../../../../docs/architecture/workers/replicas-and-idempotency.md) heartbeat PK, counters процесса vs global items.
- [scraping-resilience.md](../../../../../docs/architecture/integrations/scraping-resilience.md) § Монитор.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) UI counts failed/degraded; P0 circuit.
- [recovery.md](../../../../../docs/architecture/reliability/recovery.md) кнопка ≠ retry item.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) monitor.*, heartbeat_stale_seconds, events.schedule_tick.
- Не кэшировать /monitor.

## Acceptance Criteria

- [x] Две Catalog replica → две строки.
- [x] Stale по observed_at.
- [x] POST не ждёт воркеров.
- [x] SSE обновляет без reload.
- [x] Браузер: монитор + кнопка + список игр согласованы после tick (хотя бы появление run).

## Constraints

- UI не знает имён воркеров как RPC.
- Браузер не подключается к Kafka.
