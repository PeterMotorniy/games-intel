# Games Endpoints — Index

## Overview

Реализовать GET games, games/{slug}, platforms, media/covers, healthz/readyz. Родитель: [Phase_2_query-api](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Данные для экранов списка и карточки.
- **Success Metrics**: Контрактные тесты API.
- **Parent Alignment**: Обязательный UI backend.

### Technical

- **Primary Technical Objective**: Сервисы чтения + роутеры FastAPI; CoverStorage load.
- **Implementation Scope**: POST /runs и /monitor — Epic 6 (404 пока недопустимо если уже в OpenAPI — лучше не включать до Epic 6).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Read models; repos; covers dir.

## Deliverables

Эндпоинты + интеграционные тесты БД фикстур.

## Notes

`CatalogQueryService` / `CoverQueryService` / `HealthService` читают репозитории; SQL в `packages/db`.
