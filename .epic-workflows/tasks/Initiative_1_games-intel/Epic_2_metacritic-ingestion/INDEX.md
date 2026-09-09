# Metacritic Ingestion — Index

## Overview

Обязательный сбор игр: Playwright HTTP-sidecar, fail-closed listing, Scheduler (тик → run + source/page), Discovery (canary + 20 игр + `daily_processed_slugs`), Catalog (карточка) и локальные обложки.

Пункты 1–2 Implementation Plan (sidecar + Discovery/Catalog) в [system-architecture.md](../../../../docs/architecture/core/system-architecture.md).

## Goals

### Business

- **Primary Business Objective**: В БД появляются реальные карточки с Metacritic по правилам выборки ТЗ.
- **Business Impact**: Без этого эпика нет каталога для UI и similarity.
- **User Value**: Список игр наполняется каждый час / по кнопке.
- **Success Metrics**: Первый run дня — New Releases; listing fail не двигает курсор; 404 одной игры не валит run.
- **Parent Alignment**: Обязательная выборка и поля карточки из [task.md](../../../../task.md) / инициативы.

### Technical

- **Primary Technical Objective**: `apps/scrape/metacritic` + `packages/adapters/metacritic` + `packages/adapters/media` + SchedulerWorker + DiscoveryWorker + CatalogWorker.
- **Technical Impact**: Единый rate limit и Chromium; воркеры не знают селекторов; реплики Catalog ходят в один sidecar.
- **Implementation Scope**: Нет отзывов, LLM, YouTube, similarity, UI (кроме отдачи файла обложки можно отложить в Epic 4, но CoverStorage пишется здесь).
- **Quality Standards**: Golden HTML; parse_error = P0; тесты парсера без сети.
- **Parent Alignment**: [adapters.md](../../../../docs/architecture/integrations/adapters.md), [scraping-resilience.md](../../../../docs/architecture/integrations/scraping-resilience.md), [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md) (Scheduler, Discovery, Catalog).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1: settings, contracts (`ScheduleTick`, `RunRequested`, `GameDiscovered`, `GameCataloged`), БД, daemon loop, Compose postgres/kafka.

## Deliverables

- Sidecar HTTP JSON с теми же DTO, что Port.
- Fail-closed парсер + фикстуры + cache + circuit + canary.
- SchedulerWorker: tick → run; rule new_releases vs browse; optional similarity.recompute cron (можно заглушить publish до Epic 4, но ключи конфига уже есть).
- DiscoveryWorker: listing 20, фильтр суток, `game.discovered`.
- CatalogWorker: срез карточки + CoverStorage.

## Child tasks

| # | Phase |
|---|-------|
| 1 | [Phase_1_scrape-sidecar](Phase_1_scrape-sidecar/INDEX.md) |
| 2 | [Phase_2_scheduler-discovery](Phase_2_scheduler-discovery/INDEX.md) |
| 3 | [Phase_3_catalog-covers](Phase_3_catalog-covers/INDEX.md) |

## Notes

`adapters.metacritic.mode=in_process` — только тесты. Реплики **не** поднимают свой Chromium.
