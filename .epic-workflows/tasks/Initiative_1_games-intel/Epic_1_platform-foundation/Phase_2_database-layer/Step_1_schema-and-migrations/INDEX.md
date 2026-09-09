# Schema and Migrations — Index

## Overview

Alembic миграция 0001: `CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;` и все таблицы data-model. Родитель: [Phase_2_database-layer](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Чистая БД стенда поднимается миграциями.
- **Success Metrics**: upgrade/downgrade (или irreversible) документированы.
- **Parent Alignment**: Целостность фазы БД.

### Technical

- **Primary Technical Objective**: Точная схема [data-model.md](../../../../../../docs/architecture/database/data-model.md) § все таблицы.
- **Implementation Scope**: Только DDL/ORM mapping, без методов репозиториев (кроме моделей).
- **Quality Standards**: timestamptz; FK; check letsplay_status; unique перечисленные в data-model.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- packages/settings (vector_dim).
- Test Postgres.

## Deliverables

`packages/db` модели SQLAlchemy 2, Alembic env, revision 0001, интеграционный тест миграции с нуля.

## Notes

`external_page_cache` и `adapter_health` нужны sidecar (Epic 2), но создаются сразу, чтобы API монитора мог читать.
