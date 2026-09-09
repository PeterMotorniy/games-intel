# Idempotent Daemon Loop — Index

## Overview

Общий Python consumer loop для всех воркеров: parse CloudEvent → schema DLQ → processed_events → handler → persist+outbox → commit offset; retry Transient; heartbeat. Родитель: [Phase_3_daemon-runtime](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Одна игра не обрабатывается дважды при rebalance.
- **Success Metrics**: Параллельный второй handler — no-op.
- **Parent Alignment**: Реплики инициативы.

### Technical

- **Primary Technical Objective**: Переиспользуемый DaemonLoop + retry helper + маппинг AdapterError.
- **Implementation Scope**: Handler — protocol/callback; тестовый fake handler.
- **Quality Standards**: Структурные логи run_id/slug/worker/event_id без секретов.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 kafka-outbox, repositories, exceptions.

## Deliverables

Библиотека цикла; tenacity/эквивалент только здесь; тесты: duplicate event_id, duplicate business key новый id, schema poison, transient then success, max attempts fail.
