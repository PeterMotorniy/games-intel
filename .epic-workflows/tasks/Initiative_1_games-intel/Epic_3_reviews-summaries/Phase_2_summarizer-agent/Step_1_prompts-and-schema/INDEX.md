# Prompts and Schema — Index

## Overview

Файлы промптов с явным контрактом вывода ReviewSummary × 2; Pydantic I/O агента. Родитель: [Phase_2_summarizer-agent](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Версионируемые промпты без сборки строк в коде.
- **Success Metrics**: Контракт likes/dislikes/summary.
- **Parent Alignment**: AGENTS.md § 5.

### Technical

- **Primary Technical Objective**: Шаблон + модели ReviewSummarizerInput/Output.
- **Implementation Scope**: Не граф runtime (можно лёгкий unit на шаблоне).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- packages/contracts ReviewSummary.

## Deliverables

Prompt file versioned; input lists ReviewSnippet; комментарий контракта в шаблоне.

## Notes

Шаблон: `packages/agents/review_summarizer/prompts/prompt.md`. Путь — `prompts.review_summarizer_path`. I/O — `ReviewSummarizerInput` / `ReviewSummarizerOutput`.
