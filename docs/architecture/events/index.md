# Events Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend
**Related Docs**: [event-contracts.md](event-contracts.md), [../core/configuration.md](../core/configuration.md), [../workers/replicas-and-idempotency.md](../workers/replicas-and-idempotency.md)

## Purpose

Индекс контрактов шины: CloudEvents, JSON Schema, топики Kafka, DLQ, AsyncAPI.

## Key Principles

- Один канонический формат: воркер ↔ Kafka, LLM structured output, OpenAPI.
- Имена топиков и `type` — из конфига, по умолчанию совпадают.
- Обязательный `idempotencykey` на каждом событии.
- Эволюция схем только аддитивная.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Event Contracts | Конверт, payload-модели, топики, валидация, DLQ, AsyncAPI | [event-contracts.md](event-contracts.md) |

## Diagrams / Visuals

См. [event-contracts.md](event-contracts.md).

## Trade-offs & Justifications

CloudEvents + Pydantic; ключ операции отдельно от `id` сообщения.

## Technical Details

- **Technology Stack**: CloudEvents 1.0, Pydantic v2, JSON Schema, AsyncAPI 3.0, Kafka.
- **Configuration & Env Vars**: [configuration.md](../core/configuration.md).
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: валидация фикстур событий против JSON Schema.
- **Deployment Considerations**: топики создаются инфраструктурой Compose.

## Quality Attributes

Строгая типизация, совместимость, наблюдаемость через `id` / `source` / `subject`.
