# Scrape Sidecar — Index

## Overview

HTTP JSON sidecar Playwright: listing, карточка, (заготовка отзывов), fail-closed парсер, golden HTML, cache, circuit breaker, canary. Родитель: [Epic_2_metacritic-ingestion](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Предсказуемый отказ скрейпинга вместо мусора в каталоге.
- **Success Metrics**: parse_error не двигает курсор (курсор — Discovery, но sidecar не врёт «пусто»).
- **Parent Alignment**: Главный операционный риск — scraping-resilience.

### Technical

- **Primary Technical Objective**: `apps/scrape/metacritic` + `packages/adapters/metacritic` Port.
- **Implementation Scope**: Методы list/get_game/canary обязательны; reviews methods можно заглушить 501 до Epic 3, предпочтительно сразу контракт.
- **Quality Standards**: Unit парсера без сети; sidecar не публиковать.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1: settings adapters.metacritic, contracts DTO, cache tables, exceptions.

## Deliverables

Sidecar HTTP, клиент Port для воркеров, фикстуры Metacritic, cache+circuit+canary.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_sidecar-http-playwright](Step_1_sidecar-http-playwright/INDEX.md) |
| 2 | [Step_2_parser-fixtures](Step_2_parser-fixtures/INDEX.md) |
| 3 | [Step_3_cache-circuit-canary](Step_3_cache-circuit-canary/INDEX.md) |

## Notes

mode=in_process только тесты. N воркеров — одна очередь sidecar.
