# Reviews Worker Phase — Index

## Overview

Методы Port отзывов и демон ReviewsWorker без вызова LLM (вызов — следующая фаза; здесь можно вызвать agent protocol). Родитель: [Epic_3_reviews-summaries](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Урезанные отзывы доходят до агента как data.
- **Success Metrics**: HTML не в БД; пустые батчи → skip agent.
- **Parent Alignment**: Детерминированный сбор перед ИИ.

### Technical

- **Primary Technical Objective**: get_critic_reviews / get_user_reviews + ReviewsWorker persist/outbox.
- **Implementation Scope**: Agent invoke в Step 2 этой фазы — daemon wiring; реализация графа — Phase 2.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Sidecar; game.discovered; GameReviewsRepository; ReviewSummary models.

## Deliverables

Parser reviews на фикстурах; worker daemon; skip empty.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_reviews-port](Step_1_reviews-port/INDEX.md) |
| 2 | [Step_2_reviews-daemon](Step_2_reviews-daemon/INDEX.md) |
