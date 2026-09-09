# Metacritic Ingestion — Requirements

## Functional Requirements

- Первый успешный `new_releases` за `process_date` → source New Releases; иначе browse `last_browse_page+1`. Лимит = `scheduler.default_limit`.
- «Сегодня не обрабатывал» = нет строки `daily_processed_slugs(process_date, slug)`. Canary slug в сутки не пишется.
- Пустая страница при маркерах на месте или все slug уже сегодня → курсор +1, run completed, без `game.discovered`.
- Listing timeout / 5xx / `circuit_open` / `parse_error` / canary fail → курсор **не** двигать, run failed (для listing). См. матрицу [error-handling.md](../../../../docs/architecture/reliability/error-handling.md).
- Catalog пишет только свой срез: title, cover, publisher, genres, release_date, developer, description, video_url, platforms+scores. Чужие колонки не трогает.
- Нет видео или обложка не скачалась → null + warning, стадия completed.

## Technical Requirements

- MetacriticPort методы: `canary_parse`, `list_new_releases`, `list_browse_page`, `get_game` — [adapters.md](../../../../docs/architecture/integrations/adapters.md).
- Селекторы, маркеры, пути, TTL, circuit — только `adapters.metacritic.*` в [configuration.md](../../../../docs/architecture/core/configuration.md).
- Fail-closed, golden fixtures, page cache, circuit, canary, вежливость — [scraping-resilience.md](../../../../docs/architecture/integrations/scraping-resilience.md).
- Scheduler/Discovery/Catalog — [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md).
- Tick: `tick_source=external` канон; advisory lock + unique run — [replicas-and-idempotency.md](../../../../docs/architecture/workers/replicas-and-idempotency.md).
- События: [event-contracts.md](../../../../docs/architecture/events/event-contracts.md) — `ScheduleTick`, `RunRequested`, `GameDiscovered`, `GameCataloged`, `PlatformScore`.
- CoverStorage: ключ slug; UI URL `/api/v1/media/covers/{slug}` (эндпоинт можно включить в Epic 4, запись файла — здесь).

## Acceptance Criteria

- [ ] Фикстуры New Releases / browse / card разбираются текущими селекторами в CI без сети.
- [ ] Отсутствие DOM-маркеров → `parse_error`, курсор стоит, нет мусорных `game.discovered`.
- [ ] Canary fail → listing не вызывается.
- [ ] Circuit open → `circuit_open` → Transient у воркера.
- [ ] Два tick на одну (date, source, page) cron → один run.
- [ ] Повтор Discovery той же игры в сутки → no-op по PK daily_processed_slugs.
- [x] Catalog 404 → item failed, без retry; run не failed.
- [x] Cover битые байты не пишутся; `cover_url=null`.

## Constraints

- Воркеры не конструируют URL Metacritic и не содержат CSS-селекторов.
- Не параллелить десятки вкладок «чтобы успеть 20 игр».
- Не считать 0 игр успехом, если маркеры listing отсутствуют.
- Sidecar не публиковать наружу docker network.
