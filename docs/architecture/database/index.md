# Database Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend
**Related Docs**: [data-model.md](data-model.md), [../reliability/error-handling.md](../reliability/error-handling.md), [../reliability/recovery.md](../reliability/recovery.md)

## Purpose

Индекс модели данных PostgreSQL: домен игр, состояние пайплайна, outbox, векторный поиск.

## Key Principles

- Схема только миграциями Alembic.
- Стабильный ключ игры — `metacritic_slug`, не человекочитаемое название.
- Запись домена и outbox-события в одной транзакции.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Data Model | Таблицы, ключи, outbox, pgvector, миграции | [data-model.md](data-model.md) |

## Diagrams / Visuals

См. ER-описание в [data-model.md](data-model.md).

## Trade-offs & Justifications

Одна PostgreSQL на домен, пайплайн, outbox и unique идемпотентности.

## Technical Details

- **Technology Stack**: PostgreSQL 16, pgvector, SQLAlchemy 2, Alembic.
- **Configuration & Env Vars**: `DATABASE_URL`.
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: миграции на чистой БД, интеграционные тесты репозиториев.
- **Deployment Considerations**: один инстанс на демо; расширение pgvector обязательно.

## Quality Attributes

Целостность, идемпотентность, обратимость миграций либо явная пометка irreversible.
