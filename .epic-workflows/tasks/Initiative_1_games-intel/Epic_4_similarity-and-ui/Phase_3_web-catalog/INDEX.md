# Web Catalog Phase — Index

## Overview

React SPA: список с поиском/фильтром/сортировкой и карточка с similar. Родитель: [Epic_4_similarity-and-ui](../INDEX.md). Монитор — Epic 6.

## Goals

### Business

- **Primary Business Objective**: Пользователь выполняет сценарии обязательного UI ТЗ.
- **Success Metrics**: Empty/loading/error; клик similar; a11y.
- **Parent Alignment**: task.md веб-интерфейс.

### Technical

- **Primary Technical Objective**: apps/web Vite React TS TanStack Query Router; типы из OpenAPI.
- **Implementation Scope**: Нет обязательного SSE монитора.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Query API; codegen types.

## Deliverables

Страницы list и game; компоненты; a11y; проверка в браузере.

## Child tasks

| # | Step | Status |
|---|------|--------|
| 1 | [Step_1_list-filters](Step_1_list-filters/INDEX.md) | Completed |
| 2 | [Step_2_game-card](Step_2_game-card/INDEX.md) | Completed |

## Notes

Реализация: `apps/web`. Типы из `openapi.json` (генерация `python -m games_intel.api.openapi` + `npm run generate:api`). Монитор SSE — Epic 6.
