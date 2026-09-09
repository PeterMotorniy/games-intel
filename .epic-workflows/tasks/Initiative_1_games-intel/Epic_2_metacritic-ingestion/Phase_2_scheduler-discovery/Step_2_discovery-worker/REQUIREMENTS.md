# Discovery Worker — Requirements

## Functional Requirements

- Consume `ingestion.run.requested`; limit из события/settings.
- Если canary_enabled: canary_parse; fail → run failed, курсор стоит, listing нет.
- list_new_releases vs list_browse_page по source.
- Отфильтровать slug из daily_processed_slugs за process_date.
- Для новых: insert games draft (slug, title, listing_url), daily_processed_slugs, item stage discovered, outbox GameDiscovered (position 0..19).
- Ключ игры metacritic_slug.
- Пустая страница (маркеры ок) или 0 новых slug → курсор +1, run completed.
- timeout/5xx/circuit_open → Transient, курсор нет; parse_error → fail-closed P0, курсор нет, run failed.
- ingestion_runs.status=failed только если listing не получен; провал отдельных игр не применим (игр ещё нет).

## Technical Requirements

- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) DiscoveryWorker Failure Modes.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) flowchart Discovery.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) Discovery rows.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) GameDiscovered поля.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) daily_processed_slugs, cursors.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) listing crash.
- Consumer group discovery; control partitions.
- Две реплики безопасны unique slug/day.

## Acceptance Criteria

- [x] 20 DTO → 20 events; уже виденные отфильтрованы.
- [x] parse_error: 0 events, cursor unchanged.
- [x] circuit_open: retry/fail по Transient политике, cursor unchanged.
- [x] Canary slug не в daily_processed_slugs.
- [x] Идемпотентный повтор run event не дублирует discovered.

## Constraints

- Не публиковать частично распознанный мусор.
- Не двигать курсор до успеха включая «пусто» и «все сегодня».
- Нет LLM.
