# Repositories — Index

## Overview

Границы записи: каждый воркер пишет свой срез через repository-методы, не `UPDATE games SET *`. SQL только в `packages/db`. Родитель: [Phase_2_database-layer](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Повторный обход отзывов не уничтожает обложку и летсплей.
- **Success Metrics**: Тест reviews не затирает cover.
- **Parent Alignment**: Принцип срезов data-model.

### Technical

- **Primary Technical Objective**: Репозитории из таблицы [data-model.md](../../../../../../docs/architecture/database/data-model.md) § Репозитории.
- **Implementation Scope**: Методы upsert срезов, cursor, runs, items, processed_events, outbox claim, heartbeats, similar replace set.
- **Quality Standards**: Параметризация; никаких конкатенаций SQL.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 schema.

## Deliverables

GameCatalogRepository, GameReviewsRepository, GameLetsPlayRepository, SimilarGamesRepository, IngestionRepository, OutboxRepository + unit/integration на фикстурах БД.

## Notes

Optional `SELECT … FOR UPDATE` на ingestion_items по `(run_id, slug, stage)` с `lease_seconds` — заложить метод, используют демоны Phase 3 / воркеры.
