# Scheduler Worker — Requirements

## Functional Requirements

- Consume `kafka.events.schedule_tick` (group scheduler).
- process_date из события или timezone now.
- Правило: нет успешного new_releases за дату → source=`scheduler.new_releases_source`, page=null; иначе browse `scheduler.browse_source`, page=last_browse_page+1.
- limit = scheduler.default_limit.
- trigger cron|manual из tick.
- Unique (process_date, source, page) для cron не-failed; manual — новый run_id.
- pg_try_advisory_lock(scheduler.advisory_lock_key) на открытие run.
- tick_dedup_window_seconds для in_process.
- По similarity.full_recompute_cron: CloudEvent similarity.recompute.requested scope=all, reason=schedule; idempotency `{recompute_type}:{process_date}:{yyyy-mm-ddTHH}:all:recompute`.

## Technical Requirements

- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) SchedulerWorker.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) scheduler.*, similarity.full_recompute_cron, events.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) tick table.
- [similarity.md](../../../../../../docs/architecture/workers/similarity.md) § Расписание scope=all (producer Scheduler).
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) ScheduleTick, RunRequested, SimilarityRecomputeRequested.
- tick_source external канон; in_process для dev.

## Acceptance Criteria

- [x] Дубль tick → unique run no-op.
- [x] Первый tick дня — new_releases.
- [x] После done new_releases — browse page 1 (или last+1).
- [x] Не знает имя SimilarityWorker — только event type из конфига.
- [x] БД down → не ready (health).

## Constraints

- Нет адаптеров Metacritic.
- Интервал не хардкод 3600 в коде — settings.
