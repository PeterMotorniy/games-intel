# Cache Circuit Canary — Index

## Overview

Page cache `external_page_cache`, circuit breaker + зеркало `adapter_health`, canary_parse известного slug. Родитель: [Phase_1_scrape-sidecar](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Повторы и рестарты не долбят Metacritic; P0 видно в мониторе.
- **Success Metrics**: circuit_open отдаётся воркеру; canary fail блокирует listing.
- **Parent Alignment**: scraping-resilience P0.

### Technical

- **Primary Technical Objective**: TTL cache с ключом url_hash; states closed/open/half_open; canary_slug.
- **Implementation Scope**: UI монитора — Epic 6 читает adapter_health; здесь запись.
- **Quality Standards**: Неудачный разбор не помечает кеш как валидный listing.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1–2 parser; DB tables cache/health.

## Deliverables

Реализация cache/circuit/canary, тесты fake clock, запись adapter_health.
