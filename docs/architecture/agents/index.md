# Agents Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend
**Related Docs**: [agent-catalog.md](agent-catalog.md), [../workers/worker-catalog.md](../workers/worker-catalog.md)

## Purpose

Индекс ИИ-агентов: только шаги с языковой/STT-моделью. Kafka-демоны описаны в `workers/`.

## Key Principles

- Нет агента без задачи, которую нельзя решить детерминированно.
- LangChain + LangGraph — для LLM-агентов (резюме, заключение). STT — SttPort (OpenAI Whisper API). Демоны эти пакеты не используют.
- Агент не ходит во внешние сайты и не читает шину.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Agent Catalog | ReviewSummarizer, Transcription, LetsPlayAnalyst | [agent-catalog.md](agent-catalog.md) |

## Diagrams / Visuals

См. каталог агентов.

## Trade-offs & Justifications

Узкий каталог: читатель сразу видит, где в системе вообще есть LLM.

## Technical Details

- **Technology Stack**: LangGraph, LangChain, ChatOpenAI.
- **Configuration & Env Vars**: [configuration.md](../core/configuration.md).
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: structured output на фикстурах.
- **Deployment Considerations**: библиотека внутри образа воркера, не отдельный consumer.

## Quality Attributes

Малая поверхность ИИ, трассируемость, тестируемость без Kafka.
