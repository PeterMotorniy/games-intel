# SSE and Manual Run — Requirements

## Functional Requirements

- SSE кадры как снимок monitor (heartbeat / item updates).
- POST /runs тело опционально пустое; 202 + run_accepted; не ждать воркеров.
- Event type kafka.events.schedule_tick, trigger=manual, process_date из PROCESS timezone.
- Кнопка «Запустить сейчас»: disabled in-flight; toast 202; не retry slug.
- aria-live debounce; не кэшировать /monitor.
- Empty списка может ссылаться на монитор.

## Technical Requirements

- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) POST /runs, stream, кнопка, a11y.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) events.schedule_tick.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) UI POST один tick независимо от N scheduler.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) § 7 кнопка = новый tick.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) replay той же страницы если курсор стоит.
- source CloudEvent `urn:{app.name}:api`.
- Reverse-proxy: / static, /api proxy.

## Acceptance Criteria

- [x] SSE без EventSource ошибок на happy path.
- [x] POST пишет outbox; Scheduler создаёт run.
- [x] Кнопка не double-submit.
- [x] Браузер: монитор обновляется, tick виден в runs.
- [x] Карточка/список после ingest не ломаются (регрессия Epic 4).

## Constraints

- Не допинывать stuck item из UI.
- Не светить брокер.
