# Scheduler and Discovery — Index

## Overview

SchedulerWorker (tick → run + source/page + similarity.recompute cron) и DiscoveryWorker (canary + listing 20 + фильтр суток + game.discovered). Родитель: [Epic_2_metacritic-ingestion](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Правило выборки ТЗ: New Releases раз в сутки, далее browse pages, без повторных slug за день.
- **Success Metrics**: Курсор стоит при listing fail.
- **Parent Alignment**: Выборка Metacritic system-architecture.

### Technical

- **Primary Technical Objective**: Два демона без LLM и без знания имён соседей.
- **Implementation Scope**: Similarity recompute event publish (consumes Epic 4).
- **Quality Standards**: Unique run + advisory lock; unique daily slugs.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1 daemon; Phase 1 sidecar Port.

## Deliverables

apps/workers/scheduler, apps/workers/discovery; тесты fake Port.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_scheduler-worker](Step_1_scheduler-worker/INDEX.md) |
| 2 | [Step_2_discovery-worker](Step_2_discovery-worker/INDEX.md) |

## Notes

Канон tick_source=external — один cron-контейнер (полный сервис cron — Epic 6, здесь in_process допустим для тестов).
