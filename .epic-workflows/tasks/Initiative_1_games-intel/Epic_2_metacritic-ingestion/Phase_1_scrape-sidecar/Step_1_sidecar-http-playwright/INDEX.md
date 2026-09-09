# Sidecar HTTP Playwright — Index

## Overview

Контейнер `apps/scrape/metacritic`: Playwright, HTTP JSON API с DTO Port, очередь запросов, delay, browser pool. Родитель: [Phase_1_scrape-sidecar](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Один Chromium на все реплики Catalog/Discovery/Reviews.
- **Success Metrics**: Воркеры ходят на sidecar_base_url, не на metacritic.com.
- **Parent Alignment**: Изоляция Playwright.

### Technical

- **Primary Technical Objective**: HTTP JSON те же Pydantic DTO; timeout_seconds; pool_size default 1.
- **Implementation Scope**: Транспорт и навигация; детальный fail-closed — Step 2; circuit — Step 3.
- **Quality Standards**: Resource limits на Chromium; сеть только docker.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Settings, contracts GameListing/GameDetails.

## Deliverables

Sidecar app, Dockerfile с Chromium, httpx-клиент Port `mode=sidecar`, fake in_process для тестов каркаса.
