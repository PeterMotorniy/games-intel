# Schema and Migrations — Requirements

## Functional Requirements

Создать таблицы:

- `games` (все колонки включая embedding vector, embedding_input_hash, reviews json, letsplay_*).
- `game_platforms` PK `(game_id, platform_code)`.
- `similar_games` PK `(game_id, similar_game_id)`, check `game_id <> similar_game_id`, score hybrid, score_vector nullable, rank.
- `ingestion_cursors`, `ingestion_runs`, `ingestion_items`, `daily_processed_slugs`.
- `processed_events`, `outbox`, `worker_heartbeats`.
- `external_page_cache` PK `url_hash`.
- `adapter_health`.

Индексы: trgm title, platform_code, genres GIN. Не HNSW.

## Technical Requirements

- [data-model.md](../../../../../../docs/architecture/database/data-model.md) — колонки, unique, stages `discovered|cataloged|reviews|letsplay|similar`, statuses items `pending|running|completed|failed|degraded`, runs `requested|running|completed|failed`.
- Частичный unique index cron runs — «не более одного не-failed на (process_date, source, page)».
- `database.auto_migrate` false в prod default — [configuration.md](../../../../../../docs/architecture/core/configuration.md).
- asyncpg + SQLAlchemy 2.

## Acceptance Criteria

- [x] Тест: alembic upgrade head на пустой БД.
- [x] Unique daily_processed_slugs дубль падает.
- [x] Unique processed_events по event_id и по idempotency_key.
- [x] Vector колонка размерности из settings.
- [x] Все timestamps timestamptz.

## Constraints

- Смена embedding модели позже — irreversible rebuild, не в 0001.
- Не создавать таблицы PostgresSaver.
