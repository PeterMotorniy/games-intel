# Compose Infra — Index

## Overview

Docker Compose: PostgreSQL 16 с vector/pg_trgm, Kafka 3.x KRaft, init-контейнер топиков из конфига. Родитель: [Phase_3_daemon-runtime](../INDEX.md). Воркеры/api/web/sidecar — заглушки сервисов или только infra; полные образы в Epic 6.

## Goals

### Business

- **Primary Business Objective**: Локальный стенд БД и шины для всех следующих эпиков.
- **Success Metrics**: `compose up` postgres+kafka ready.
- **Parent Alignment**: Deployment Considerations system-architecture.

### Technical

- **Primary Technical Objective**: `infra/compose/` postgres, kafka, topic init; volume postgres.
- **Implementation Scope**: Не обязательно все воркеры; healthchecks обязательны.
- **Quality Standards**: Секреты из env; replication_factor 1 на демо.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Settings (имена топиков, partitions).

## Deliverables

compose yaml, init topics script читающий те же имена, что settings defaults, README фрагмент запуска infra, тест/скрипт проверки брокера (опционально).
