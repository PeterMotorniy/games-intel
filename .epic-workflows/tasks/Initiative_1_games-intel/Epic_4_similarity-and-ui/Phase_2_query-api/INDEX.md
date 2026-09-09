# Query API Phase — Index

## Overview

FastAPI read-модель каталога: OpenAPI, список/карточка/платформы/обложки/health. POST /runs можно заглушить до Epic 6, контракт пути заложить. Родитель: [Epic_4_similarity-and-ui](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Браузер получает данные каталога.
- **Success Metrics**: Фильтр, поиск, сортировка, 404 slug, 503 без БД.
- **Parent Alignment**: UI обязательной части.

### Technical

- **Primary Technical Objective**: apps/api; RFC 7807; codegen OpenAPI.
- **Implementation Scope**: Нет LLM; нет RPC воркерам.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Repositories read; covers volume; settings api.*.

## Deliverables

Эндпоинты, OpenAPI, тесты на фикстурах БД.

## Child tasks

| # | Step | Status |
|---|------|--------|
| 1 | [Step_1_read-models-openapi](Step_1_read-models-openapi/INDEX.md) | Completed |
| 2 | [Step_2_games-endpoints](Step_2_games-endpoints/INDEX.md) | Completed |

## Notes

Реализация: `apps/api`. POST `/runs` и `/monitor` не включены в OpenAPI (Epic 6).
