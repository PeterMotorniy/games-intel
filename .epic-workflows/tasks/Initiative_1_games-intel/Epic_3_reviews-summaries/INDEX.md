# Reviews Summaries — Index

## Overview

Скачивание отзывов критиков и пользователей через MetacriticPort (детерминированно) и structured резюме «что нравится / нет» через ReviewSummarizerAgent. Пункт 3 Implementation Plan.

## Goals

### Business

- **Primary Business Objective**: В карточке игры появляются отдельные резюме критиков и пользователей на русском.
- **Business Impact**: Ключевая ИИ-часть обязательного ТЗ.
- **User Value**: Коротко понять сильные и слабые стороны без чтения всех отзывов.
- **Success Metrics**: Два блока ReviewSummary; пустые отзывы → degraded без вызова модели; повтор обхода может обновить резюме.
- **Parent Alignment**: Поля резюме из [task.md](../../../../task.md); агент только здесь из обязательной части.

### Technical

- **Primary Technical Objective**: ReviewsWorker + `packages/agents/review_summarizer` (LangGraph structured output, LangSmith, PostgresSaver).
- **Technical Impact**: LLM изолирован; демон ретраит адаптер, агент — только модель/схему.
- **Implementation Scope**: Нет YouTube. Similarity `recompute_on_reviews` — Epic 4 (событие `game.reviews.summarized` уже публикуется).
- **Quality Standards**: Промпт-файл с контрактом; без regex по свободному тексту; тесты fake LLM.
- **Parent Alignment**: [agent-catalog.md](../../../../docs/architecture/agents/agent-catalog.md), [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md) ReviewsWorker.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1 (daemon, contracts `GameReviewsSummarized` / `ReviewSummary`).
- Epic 2 sidecar: методы `get_critic_reviews` / `get_user_reviews` реализуются в этом эпике (Phase 1), поверх того же sidecar.

## Deliverables

- Port-методы отзывов, урезанные `ReviewSnippet`, без HTML.
- ReviewsWorker: skip агента если пусто; persist только reviews-колонок.
- ReviewSummarizerAgent: русский язык, likes/dislikes/summary × 2.
- Тесты матрицы пустых отзывов / LLM schema retry.

## Child tasks

| # | Phase |
|---|-------|
| 1 | [Phase_1_reviews-worker](Phase_1_reviews-worker/INDEX.md) |
| 2 | [Phase_2_summarizer-agent](Phase_2_summarizer-agent/INDEX.md) |

## Notes

`langgraph-checkpoint-postgres` только в образе Reviews (и позже LetsPlay).
