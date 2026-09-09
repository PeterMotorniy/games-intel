# Settings and Contracts — Index

## Overview

Монорепозиторий, tooling качества, пакет типизированных settings и канонические Pydantic-контракты CloudEvents/JSON Schema/AsyncAPI. Родитель: [Epic_1_platform-foundation](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Любой стенд меняет топики, cron и лимиты конфигом, не релизом логики.
- **Business Impact**: Снижение регрессий «опечатка в имени топика».
- **User Value**: Косвенный.
- **Success Metrics**: Strict parse на старте; snapshot example-конфига; golden JSON событий.
- **Parent Alignment**: Фундамент эпика 1.

### Technical

- **Primary Technical Objective**: `packages/settings` + `packages/contracts` + uv workspace + линтеры.
- **Technical Impact**: Единый source of truth для шины и LLM structured output.
- **Implementation Scope**: Нет БД и Kafka runtime (только модели сообщений).
- **Quality Standards**: Pydantic v2; эволюция схем только аддитивная.
- **Parent Alignment**: [configuration.md](../../../../../docs/architecture/core/configuration.md), [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

Нет кодовых зависимостей внутри инициативы.

## Deliverables

uv workspace, ruff/mypy/pytest, example config, полный settings tree, все payload-модели, генерация JSON Schema и `contracts/asyncapi.yaml`.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_monorepo-and-tooling](Step_1_monorepo-and-tooling/INDEX.md) |
| 2 | [Step_2_typed-settings](Step_2_typed-settings/INDEX.md) |
| 3 | [Step_3_event-contracts](Step_3_event-contracts/INDEX.md) |

## Notes

Имена type/topic — defaults из конфига; в коде только `settings.kafka.events.*`.
