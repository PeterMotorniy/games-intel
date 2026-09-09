# Platform Foundation — Index

## Overview

Каркас платформы, без которого нельзя писать воркеры: монорепо и tooling, типизированные settings, контракты CloudEvents, схема PostgreSQL + репозитории, Kafka/outbox, общий цикл демона с идемпотентностью, Compose для postgres+kafka.

Соответствует пункту 1 Implementation Plan: «Контракты, миграции, каркас демона» в [system-architecture.md](../../../../docs/architecture/core/system-architecture.md).

## Goals

### Business

- **Primary Business Objective**: Снять риск «потом перепишем шину/схему»: все эпики пайплайна садятся на один контракт и одну БД.
- **Business Impact**: Дальнейшие эпики можно сдавать независимо (воркеры автономны).
- **User Value**: Косвенный — без фундамента нет каталога и монитора.
- **Success Metrics**: Процесс стартует со strict settings; топики создаются из конфига; миграции на чистой БД; тестовый handler идемпотентен.
- **Parent Alignment**: База для всей инициативы [Initiative_1_games-intel](../INDEX.md).

### Technical

- **Primary Technical Objective**: Пакеты `packages/settings`, `packages/contracts`, `packages/db`, `packages/kafka` + каркас демона + Compose infra.
- **Technical Impact**: Единый контракт Pydantic → JSON Schema → CloudEvents; unique idempotency; SQL не покидает `packages/db`.
- **Implementation Scope**: Нет Metacritic/YouTube/LLM/UI в этом эпике.
- **Quality Standards**: Strict settings; golden JSON событий; миграции обратимы либо irreversible явно; тесты без сети.
- **Parent Alignment**: Канон [configuration.md](../../../../docs/architecture/core/configuration.md), [event-contracts.md](../../../../docs/architecture/events/event-contracts.md), [data-model.md](../../../../docs/architecture/database/data-model.md), [replicas-and-idempotency.md](../../../../docs/architecture/workers/replicas-and-idempotency.md).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Архитектурные документы выше.
- Нет внешних API.

## Deliverables

- Рабочий uv-workspace, ruff/mypy/pytest, `.env.example`, `config.example.yaml`.
- Полное дерево settings и пакет контрактов + генерация JSON Schema/AsyncAPI.
- Alembic 0001: домен + pipeline + outbox + heartbeats + cache + adapter_health + extensions.
- Библиотека consumer loop: validate → processed_events → handler → persist+outbox → commit offset.
- Compose: PostgreSQL 16 (vector, pg_trgm), Kafka KRaft, init-топики.

## Child tasks

| # | Phase | Focus |
|---|-------|--------|
| 1 | [Phase_1_settings-and-contracts](Phase_1_settings-and-contracts/INDEX.md) | Монорепо, settings, CloudEvents |
| 2 | [Phase_2_database-layer](Phase_2_database-layer/INDEX.md) | Миграции и репозитории |
| 3 | [Phase_3_daemon-runtime](Phase_3_daemon-runtime/INDEX.md) | Kafka, outbox, цикл демона, Compose infra |

## Notes

Scheduler/Discovery/Catalog/Similarity образы **не** получают langchain на этом этапе и далее ([worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md)).
