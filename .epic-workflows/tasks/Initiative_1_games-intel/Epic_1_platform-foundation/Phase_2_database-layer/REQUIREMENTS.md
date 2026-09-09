# Database Layer — Requirements

## Functional Requirements

- Стабильный ключ игры — `metacritic_slug`.
- Каждый writer обновляет только свой набор колонок.
- Unique: slug; daily_processed_slugs PK; items `(run_id, slug, stage)`; processed_events event_id и idempotency_key; outbox idempotency_key; similar запрет self; heartbeats `(worker_type, instance_id)`.
- Частичный unique на ingestion_runs для cron `(process_date, source, page)` не-failed.

## Technical Requirements

- Полная схема: [data-model.md](../../../../../docs/architecture/database/data-model.md).
- Embedding dimension из `embeddings.vector_dim` settings.
- Индексы UI: pg_trgm GIN title, platform_code, GIN genres. HNSW не в 0001.
- `letsplay_status` check constraint.
- `ingestion_items.attempt_count` для recovery.
- Репозитории: GameCatalog, GameReviews, GameLetsPlay, SimilarGames, Ingestion, Outbox.
- Query API позже read-only + insert tick; методы чтения заложить.

## Acceptance Criteria

- [x] Alembic upgrade на чистой Postgres 16.
- [x] Unique slug/day и параллельный idempotency_key.
- [x] Rollback транзакции откатывает outbox вместе с доменом.
- [x] Self-insert similar_games невозможен.
- [x] Down-миграция 0001 либо явно irreversible с комментарием.

## Constraints

- Ручной DDL запрещён.
- SQL не протекает в сервисы/воркеры.
- Checkpoints LangGraph не создавать здесь.
