# Summarizer Agent Phase — Index

## Overview

ReviewSummarizerAgent: LangGraph structured output, промпт-файлы, LangSmith, PostgresSaver. Родитель: [Epic_3_reviews-summaries](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Русские резюме likes/dislikes/summary отдельно критики/пользователи.
- **Success Metrics**: Схема Pydantic, не regex.
- **Parent Alignment**: ИИ обязательной части ТЗ.

### Technical

- **Primary Technical Objective**: packages/agents/review_summarizer.
- **Implementation Scope**: Нет Kafka, нет MetacriticPort.
- **Quality Standards**: thread_id < 255; RetryPolicy только LLM node.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Contracts ReviewSummary; llm/langsmith settings; ReviewsWorker invoke.

## Deliverables

Промпт+схема, граф, тесты fake LLM, checkpoint wiring.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_prompts-and-schema](Step_1_prompts-and-schema/INDEX.md) |
| 2 | [Step_2_langgraph-agent](Step_2_langgraph-agent/INDEX.md) |

## Notes

`packages/agents/review_summarizer`: промпт v1, параллельный LangGraph, RetryPolicy на LLM-нодах, InMemorySaver в тестах / AsyncPostgresSaver в процессе, LangSmith `{prefix}-review-summarizer`.
