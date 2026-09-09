# Read Models OpenAPI — Index

## Overview

Pydantic read-модели проекций UI и генерация OpenAPI 3 из FastAPI. Родитель: [Phase_2_query-api](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Клиент не дублирует DTO руками.
- **Success Metrics**: Схема совпадает с полями карточки.
- **Parent Alignment**: web-ui types from OpenAPI.

### Technical

- **Primary Technical Objective**: Read DTO; problem+json; пагинация.
- **Implementation Scope**: Не обязательны monitor schemas (Epic 6), но можно заготовки.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Domain fields data-model / event-contracts.

## Deliverables

Модели списка/карточки/similar/platform; OpenAPI export; RFC 7807.

## Notes

Схемы: `apps/api/src/games_intel/api/schemas.py`. Поля nested — `PlatformScore`, `ReviewSummary`, `SimilarGameRef` из `packages/contracts`.
