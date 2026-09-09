# Catalog and Covers — Requirements

## Functional Requirements

- По game.discovered вызвать get_game(slug), upsert catalog slice + platforms replace, outbox GameCataloged.
- Поля: title, cover_url локальный, cover_source_url, developer, publisher, genres, release_date, description, video_url, platforms+scores.
- catalog.empty_video_ok default true: нет видео — null, completed.
- Обложка не скачалась — cover_url null, warning, completed.
- 404 — item failed, без retry.
- Не трогать reviews/letsplay/embedding колонки.

## Technical Requirements

- [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) CatalogWorker.
- [adapters.md](../../../../../docs/architecture/integrations/adapters.md) get_game, CoverStorage.
- [scraping-resilience.md](../../../../../docs/architecture/integrations/scraping-resilience.md) § Обложки.
- [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md) GameCataloged.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) Catalog rows.
- Реплики: partitions.game_events >= N; [replicas-and-idempotency.md](../../../../../docs/architecture/workers/replicas-and-idempotency.md).
- media.covers_dir, covers_url_prefix — [configuration.md](../../../../../docs/architecture/core/configuration.md).

## Acceptance Criteria

- [x] Fake get_game → все поля среза в БД.
- [x] 404 → failed, Reviews всё ещё может работать на discovered (изоляция).
- [x] Повтор discovered → no-op catalog.
- [x] Platforms replace атомарный.
- [x] Битые байты обложки не пишутся.

## Constraints

- Браузер не в реплике Catalog.
- Нет hotlink в cover_url проекции (локальный путь API).
