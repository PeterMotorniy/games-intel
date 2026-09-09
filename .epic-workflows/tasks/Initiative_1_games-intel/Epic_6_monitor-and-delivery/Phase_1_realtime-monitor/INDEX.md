# Realtime Monitor Phase — Index

## Overview

Heartbeats, снимок /monitor, SSE, POST /runs, UI монитора и кнопка запуска. Родитель: [Epic_6_monitor-and-delivery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Оператор видит пайплайн в реальном времени и может запустить обработку.
- **Success Metrics**: 202 tick; две строки реплик; circuit виден.
- **Parent Alignment**: task.md доп. 2.

### Technical

- **Primary Technical Objective**: API monitor + SSE из БД; UI WorkerTable; outbox schedule_tick.
- **Implementation Scope**: Не replay slug.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Workers heartbeats; adapter_health; ingestion tables; web catalog.

## Deliverables

Endpoints + monitor page + tests.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_heartbeats-and-snapshot](Step_1_heartbeats-and-snapshot/INDEX.md) |
| 2 | [Step_2_sse-and-manual-run](Step_2_sse-and-manual-run/INDEX.md) |
