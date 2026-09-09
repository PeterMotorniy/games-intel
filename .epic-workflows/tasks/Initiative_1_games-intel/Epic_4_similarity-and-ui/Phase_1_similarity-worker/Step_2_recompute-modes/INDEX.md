# Recompute Modes — Index

## Overview

Режимы inline_all и incremental (neighbors fan-out без каскада), обработка similarity.recompute.requested scope all/neighbors/game, hourly unique. Родитель: [Phase_1_similarity-worker](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Обратные ссылки: новая игра видна в чужих карточках.
- **Success Metrics**: Третья игра вытесняет rank K; neighbors без шторма.
- **Parent Alignment**: freshness корпуса.

### Technical

- **Primary Technical Objective**: Worker handlers трёх входов; mode из конфига.
- **Implementation Scope**: HNSW миграция опциональна если count < 5000.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 scorer; Scheduler recompute events.

## Deliverables

SimilarityWorker полный; тесты inline_all, incremental anti-storm, hourly no-op.
