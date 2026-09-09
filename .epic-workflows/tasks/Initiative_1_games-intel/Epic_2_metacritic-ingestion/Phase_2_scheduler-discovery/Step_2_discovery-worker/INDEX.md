# Discovery Worker — Index

## Overview

DiscoveryWorker: consume run_requested, canary+listing через Port, фильтр суток, drafts games, daily_processed_slugs, game.discovered, движение курсора только после успеха. Родитель: [Phase_2_scheduler-discovery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: До 20 новых игр за run, без повторов за календарный день.
- **Success Metrics**: Fail-closed: мусор не в шине.
- **Parent Alignment**: Обязательная выборка ТЗ.

### Technical

- **Primary Technical Objective**: apps/workers/discovery; MetacriticPort only.
- **Implementation Scope**: Не карточка get_game.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Scheduler events; sidecar Port; IngestionRepository; daemon loop.

## Deliverables

Handler listing; тесты fake Port: timeout, parse_error, empty, all-seen, happy 20.
