# Heartbeats and Snapshot — Index

## Overview

Воркеры пишут worker_heartbeats; API GET /monitor агрегирует items/runs/cursor/adapter_health. Родитель: [Phase_1_realtime-monitor](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Снимок состояния переживает рестарт UI.
- **Success Metrics**: Глобальные counts из ingestion_items, не из processed_ok процесса.
- **Parent Alignment**: Operability.

### Technical

- **Primary Technical Objective**: Heartbeat в daemon loop (если ещё не полно) + monitor service.
- **Implementation Scope**: Не SSE (следующий шаг).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Heartbeat table; items; adapter_health; event WorkerHeartbeat optional (sink может быть только БД).

## Deliverables

GET /monitor JSON; тесты агрегатов.
