# Catalog Worker — Index

## Overview

Демон CatalogWorker: consume game.discovered, Port get_game, persist catalog slice, emit game.cataloged. Родитель: [Phase_3_catalog-covers](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Карточка игры с Metacritic в БД.
- **Success Metrics**: Идемпотентность стадии cataloged; 404 = failed item.
- **Parent Alignment**: Обязательные поля кроме reviews/similar/letsplay.

### Technical

- **Primary Technical Objective**: apps/workers/catalog; CoverStorage вызов (реализация файла — соседний шаг).
- **Implementation Scope**: Не similarity.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Discovery events; get_game; GameCatalogRepository; daemon loop.

## Deliverables

Handler + тесты fake Port: happy, 404, timeout retry, missing optional fields.
