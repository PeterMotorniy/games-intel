# Scheduler Worker — Index

## Overview

Демон SchedulerWorker: consume schedule_tick, advisory lock, unique run, produce run_requested; по cron produce similarity.recompute.requested. Родитель: [Phase_2_scheduler-discovery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Часовой (конфиг) и ручной запуск — один и тот же event type.
- **Success Metrics**: Дубль tick → no-op.
- **Parent Alignment**: Триггеры пайплайна.

### Technical

- **Primary Technical Objective**: apps/workers/scheduler без langchain, без HTTP сайтов.
- **Implementation Scope**: Не Discovery listing.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Daemon loop, IngestionRepository, events.

## Deliverables

Handler tick; правило source; publish recompute; тесты unique run и lock.
