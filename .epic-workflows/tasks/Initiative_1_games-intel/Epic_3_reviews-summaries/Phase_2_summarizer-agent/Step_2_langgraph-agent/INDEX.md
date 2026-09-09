# LangGraph Review Agent — Index

## Overview

StateGraph ReviewSummarizer: 1–2 node structured output (критики/пользователи параллельно допустимо), RetryPolicy на LLM, PostgresSaver, LangSmith span. Родитель: [Phase_2_summarizer-agent](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Устойчивые резюме при глюке схемы модели.
- **Success Metrics**: Resume checkpoint не платит токены повторно (тест).
- **Parent Alignment**: recovery агентов.

### Technical

- **Primary Technical Objective**: packages/agents/review_summarizer граф; без tools.
- **Implementation Scope**: Transcription/LetsPlayAnalyst не здесь.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 prompts; llm settings; optional langgraph-checkpoint-postgres.

## Deliverables

Agent class ainvoke; tests fake chat model; image extra deps reviews worker.

## Notes

Параллельные ноды `summarize_critic` / `summarize_user`, `RetryPolicy` только на них, `thread_id={run_id}:{slug}:review_summarizer`, LangSmith project `{prefix}-review-summarizer`.
