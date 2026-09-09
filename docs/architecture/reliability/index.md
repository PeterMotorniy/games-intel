# Reliability Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend, QA
**Related Docs**: [error-handling.md](error-handling.md), [recovery.md](recovery.md), [../database/data-model.md](../database/data-model.md)

## Purpose

Индекс надёжности: **политика ошибок во время обработки** и **восстановление после рестарта процесса**. Это разные документы.

## Key Principles

- At-least-once + идемпотентные обработчики.
- Сбой одной игры не валит прогон дня.
- Транзиентные ошибки ретраятся; бизнес-ошибки — нет.
- Checkpoint LangGraph — только у ИИ-агентов.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Error Handling | Классификация, retry, DLQ, матрица стадий, что видит UI | [error-handling.md](error-handling.md) |
| Recovery | Offset, outbox, attempt_count, resume агента, runbook | [recovery.md](recovery.md) |

## Diagrams / Visuals

Сначала [error-handling.md](error-handling.md), затем [recovery.md](recovery.md).

## Trade-offs & Justifications

Два файла: политика ошибок vs рестарт. Unique `idempotency_key` и outbox закрывают реплики.

## Technical Details

- **Technology Stack**: типизированные исключения, daemon retry helper, Kafka DLQ; PostgresSaver только у агентов.
- **Configuration & Env Vars**: retry limits, backoff, DLQ topic.
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: матрица ошибок на fake Port; crash-injection демонов; resume агента.
- **Deployment Considerations**: воркеры stateless, состояние в Postgres и Kafka.

## Quality Attributes

Reliability, recoverability, observability инцидентов.
