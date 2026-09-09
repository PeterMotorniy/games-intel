# Database Layer — Index

## Overview

PostgreSQL как единственное прикладное хранилище: Alembic-миграции, SQLAlchemy 2, репозитории с границами записи по воркерам. Родитель: [Epic_1_platform-foundation](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Карточки, стадии пайплайна и идемпотентность живут в одной БД — UI читает проекцию без второй базы.
- **Business Impact**: Простота демо и целостность unique.
- **User Value**: Поиск и similar из той же БД.
- **Success Metrics**: Миграции с нуля; unique slug/day; reviews не затирает cover.
- **Parent Alignment**: Якоря состояния для всех эпиков.

### Technical

- **Primary Technical Objective**: Таблицы [data-model.md](../../../../../docs/architecture/database/data-model.md) + репозитории.
- **Technical Impact**: Домен+outbox в одной транзакции; SQL только `packages/db`.
- **Implementation Scope**: Нет HNSW (отдельная миграция позже). Нет PostgresSaver.setup (агенты).
- **Quality Standards**: timestamptz UTC; обратимость или irreversible явно.
- **Parent Alignment**: data-model.md, database/index.md.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Phase 1 contracts (типы полей совпадают с payload).
- Compose Postgres можно поднять в Phase 3; для тестов — testcontainer/локальный postgres.

## Deliverables

Миграция 0001 (extensions vector, pg_trgm + все таблицы), ORM, репозитории из таблицы Writer/Reads.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_schema-and-migrations](Step_1_schema-and-migrations/INDEX.md) |
| 2 | [Step_2_repositories](Step_2_repositories/INDEX.md) |

## Notes

Предпочтение `daily_processed_slugs` отдельно от items — канон data-model.

Реализовано в `packages/db`: Alembic revision `0001`, ORM SQLAlchemy 2, репозитории Catalog/Reviews/LetsPlay/Similar/Ingestion/Outbox. HNSW и PostgresSaver не входят в 0001.
