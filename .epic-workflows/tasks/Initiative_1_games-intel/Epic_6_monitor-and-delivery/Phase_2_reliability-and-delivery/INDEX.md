# Reliability and Delivery Phase — Index

## Overview

Матрица ошибок и recovery-тесты; полный Compose с репликами, cron, sidecar, api, web; выравнивание docs; README сдачи. Родитель: [Epic_6_monitor-and-delivery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Стенд, который можно открыть по ссылке и проверить ТЗ.
- **Success Metrics**: Тесты зелёные; compose up; docs Existing.
- **Parent Alignment**: Результат тестового + Implementation Plan п.6.

### Technical

- **Primary Technical Objective**: Test matrix error-handling + recovery; compose replicas; topic partitions ≥ replicas.
- **Implementation Scope**: Хостинг URL — env/стенд, не код.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Все эпики 1–5 функционально; monitor.

## Deliverables

Тесты; compose; README; architecture status updates.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_error-recovery-tests](Step_1_error-recovery-tests/INDEX.md) |
| 2 | [Step_2_compose-replicas-delivery](Step_2_compose-replicas-delivery/INDEX.md) |
