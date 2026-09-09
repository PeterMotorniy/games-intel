# Reviews Daemon — Index

## Overview

ReviewsWorker: Kafka game.discovered → Port → optional agent → persist reviews slice → game.reviews.summarized. Родитель: [Phase_1_reviews-worker](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Стадия reviews в пайплайне параллельно catalog/letsplay.
- **Success Metrics**: Сбой LLM не валит catalog.
- **Parent Alignment**: Хореография.

### Technical

- **Primary Technical Objective**: apps/workers/reviews; langchain только как зависимость образа из-за агента (Phase 2).
- **Implementation Scope**: Wiring agent interface; fake agent в тестах этого шага допустим.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Reviews port; daemon loop; GameReviewsRepository.

## Deliverables

Worker; тесты empty skip, persist columns, idempotency.
