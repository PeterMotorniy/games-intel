# Scheduler and Discovery — Requirements

## Functional Requirements

- Tick (cron или manual) → Scheduler решает source/page, пишет ingestion_runs, outbox `ingestion.run.requested`.
- Нет успешного new_releases за process_date → new_releases page null; иначе browse last_browse_page+1.
- Discovery: canary если включён; listing; фильтр daily_processed_slugs; черновики games; N событий game.discovered (position 0..19).
- Успешный listing (включая пусто и все уже сегодня) двигает курсор; fail — нет.

## Technical Requirements

- [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) SchedulerWorker, DiscoveryWorker.
- [system-architecture.md](../../../../../docs/architecture/core/system-architecture.md) поток суток, выборка.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) матрица Scheduler/Discovery.
- [recovery.md](../../../../../docs/architecture/reliability/recovery.md) § 4 курсор.
- События ScheduleTick, RunRequested, GameDiscovered — [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md).
- Lock/unique: [replicas-and-idempotency.md](../../../../../docs/architecture/workers/replicas-and-idempotency.md) § Tick/cron.
- process_date в `app.process_timezone`.
- По `similarity.full_recompute_cron` Scheduler публикует `kafka.events.similarity_recompute` scope=all (идемпотентность часа — Epic 4 unique, ключ заложить).

## Acceptance Criteria

- [x] Два Scheduler in_process без lock — тест показывает необходимость lock; с lock один run.
- [x] parse_error listing: курсор не +1, run failed.
- [x] Все slug сегодня: курсор +1, 0 discovered.
- [x] Canary не в daily_processed_slugs.
- [x] Discovery crash до persist: повтор listing безопасен (offset не commit).

## Constraints

- Scheduler без адаптеров сайтов и LLM.
- Discovery не знает Catalog.
- Manual run допускает повтор страницы новым run_id; фильтр суток всё равно режет slug.
