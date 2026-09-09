# Parser Fixtures — Index

## Overview

Парсер: селекторы из конфига, обязательные DOM-маркеры, golden HTML в `tests/fixtures/metacritic/`. Родитель: [Phase_1_scrape-sidecar](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Смена вёрстки Metacritic ловится CI, а не мусором в Kafka.
- **Success Metrics**: CI падает, если фикстура не разбирается.
- **Parent Alignment**: Fail-closed listing.

### Technical

- **Primary Technical Objective**: Парсер listing New Releases, browse, card (+ reviews HTML если уже есть фикстура).
- **Implementation Scope**: Без живого сайта в unit.
- **Quality Standards**: селекторы и фикстуры описывают один актуальный разбор.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 sidecar structure.

## Deliverables

Фикстуры, селекторы yaml, тесты маркеров, нормализация platform_code (ps5, pc, ns2, …).
