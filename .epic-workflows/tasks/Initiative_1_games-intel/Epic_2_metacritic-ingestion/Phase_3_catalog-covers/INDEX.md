# Catalog and Covers — Index

## Overview

CatalogWorker заполняет карточку Metacritic; CoverStorage сохраняет обложку локально. Родитель: [Epic_2_metacritic-ingestion](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: В БД полные поля обязательной карточки (кроме резюме/летсплея).
- **Success Metrics**: 404 одной игры не валит run и не останавливает Reviews/LetsPlay.
- **Parent Alignment**: Поля карточки task.md.

### Technical

- **Primary Technical Objective**: get_game + CoverStorage; produce game.cataloged; N реплик, общий sidecar.
- **Implementation Scope**: GET media endpoint может быть в Epic 4; запись файла здесь.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- game.discovered; sidecar get_game; GameCatalogRepository; media settings.

## Deliverables

apps/workers/catalog; packages/adapters/media; тесты 404, missing video/cover, idempotency.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_catalog-worker](Step_1_catalog-worker/INDEX.md) |
| 2 | [Step_2_cover-storage](Step_2_cover-storage/INDEX.md) |

## Notes

genres и release_date обязательны для hybrid similarity.
