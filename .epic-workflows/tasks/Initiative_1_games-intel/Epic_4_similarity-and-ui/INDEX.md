# Similarity and Catalog UI — Index

## Overview

Похожие игры из своей БД (hybrid kNN, reverse refresh, full recompute) и обязательный веб-интерфейс: Query API + список/карточка/фильтры/поиск/сортировка. Пункт 4 Implementation Plan.

Монитор SSE и кнопка запуска — Epic 6; здесь только каталог игр. Эндпоинт обложек включается вместе с API.

## Goals

### Business

- **Primary Business Objective**: Пользователь листает каталог, открывает полную карточку и переходит по похожим играм.
- **Business Impact**: Закрывает UI обязательной части ТЗ.
- **User Value**: Поиск, фильтр платформ, сортировка по рейтингу, similar.
- **Success Metrics**: Новичок сразу появляется в чужих списках при `inline_all`; empty/loading/error на каждом экране.
- **Parent Alignment**: Similar + UI из [task.md](../../../../task.md).

### Technical

- **Primary Technical Objective**: SimilarityWorker без LangGraph; FastAPI read-only + outbox tick заготовка (POST может быть заглушка до Epic 6, но контракт лучше сразу); React каталог.
- **Technical Impact**: Эмбеддинг только при смене hash; hybrid score в `similar_games.score`.
- **Implementation Scope**: Нет LetsPlay-блока в карточке как обязательного (поле может быть пустым). Нет SSE монитора.
- **Quality Standards**: OpenAPI → типы клиента; self в similar запрещён схемой.
- **Parent Alignment**: [similarity.md](../../../../docs/architecture/workers/similarity.md), [web-ui.md](../../../../docs/architecture/frontend/web-ui.md), [data-model.md](../../../../docs/architecture/database/data-model.md).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1: pgvector колонка, daemon, contracts.
- Epic 2: cataloged игры с genres/platforms/release_date.
- Epic 3 желателен для `recompute_on_reviews`, но catalog-only эмбеддинг обязателен первым.

## Deliverables

- SimilarityWorker: ingest cataloged/reviews/recompute; режимы inline_all и incremental.
- Query API: GET games, game, platforms, covers, healthz/readyz; OpenAPI.
- Web: список + карточка + similar + a11y.

## Child tasks

| # | Phase | Status |
|---|-------|--------|
| 1 | [Phase_1_similarity-worker](Phase_1_similarity-worker/INDEX.md) | Completed |
| 2 | [Phase_2_query-api](Phase_2_query-api/INDEX.md) | Completed |
| 3 | [Phase_3_web-catalog](Phase_3_web-catalog/INDEX.md) | Completed |

## Notes

Full recompute cron публикует Scheduler (Epic 2) событием из конфига, не RPC к Similarity.
