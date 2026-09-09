# Daemon Runtime — Index

## Overview

Kafka-клиент, outbox relay, общий цикл демона (validate → idempotency → handle → persist → commit offset), классификация ошибок, Compose postgres+kafka+init топиков. Родитель: [Epic_1_platform-foundation](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Реплики и рестарты не плодят дубли карточек.
- **Success Metrics**: Тест двух параллельных handler; poison не клинит партицию.
- **Parent Alignment**: Надёжность инициативы.

### Technical

- **Primary Technical Objective**: `packages/kafka` + shared daemon framework + `infra/compose` postgres/kafka.
- **Technical Impact**: At-least-once + идемпотентный handler; auto_commit false.
- **Implementation Scope**: Нет бизнес-handler Discovery/Catalog — только каркас + пример/тест double-handle.
- **Quality Standards**: DLQ schema; retry helper из retry.*.
- **Parent Alignment**: worker-catalog цикл; replicas; error-handling; recovery якоря.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Phase 1 contracts/settings, Phase 2 repos.

## Deliverables

Producer/consumer CloudEvents, outbox publisher loop, DaemonLoop, typed exceptions, compose files, topic init.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_kafka-outbox](Step_1_kafka-outbox/INDEX.md) |
| 2 | [Step_2_idempotent-daemon-loop](Step_2_idempotent-daemon-loop/INDEX.md) |
| 3 | [Step_3_compose-infra](Step_3_compose-infra/INDEX.md) |

## Notes

`max_poll_interval_ms` > худшего handler с retry — [configuration.md](../../../../../docs/architecture/core/configuration.md).
