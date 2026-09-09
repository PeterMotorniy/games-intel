# Workers Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend
**Related Docs**: [worker-catalog.md](worker-catalog.md), [replicas-and-idempotency.md](replicas-and-idempotency.md), [similarity.md](similarity.md), [../core/configuration.md](../core/configuration.md), [../agents/agent-catalog.md](../agents/agent-catalog.md)

## Purpose

Индекс автономных Python-демонов пайплайна. Демоны общаются только через Kafka; ИИ вызывается точечно из Reviews и LetsPlay.

## Key Principles

- Воркер не знает имён других воркеров.
- Детерминированная работа — обычный Python, не LangGraph.
- Каталог агентов — отдельно: только шаги с моделью.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Worker Catalog | Шесть демонов | [worker-catalog.md](worker-catalog.md) |
| Similarity | Hybrid kNN, reverse refresh, full recompute | [similarity.md](similarity.md) |
| Replicas | Две+ копии воркера без дублей | [replicas-and-idempotency.md](replicas-and-idempotency.md) |

## Diagrams / Visuals

См. [worker-catalog.md](worker-catalog.md), [replicas-and-idempotency.md](replicas-and-idempotency.md).

## Trade-offs & Justifications

Реплики вынесены из каталога: иначе смешиваются «что делает воркер» и «как не плодить дубли».

## Technical Details

- **Technology Stack**: Python daemons, Kafka, typed adapter ports.
- **Configuration & Env Vars**: см. каталог.
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: контрактные тесты событий и идемпотентности.
- **Deployment Considerations**: контейнер на воркер.

## Quality Attributes

Discoverability границы «демон / агент», maintainability control flow.
