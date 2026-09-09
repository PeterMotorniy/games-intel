# Similarity Worker Phase — Index

## Overview

SimilarityWorker: embedding + hybrid kNN, inline_all/incremental, reverse refresh, full recompute. Родитель: [Epic_4_similarity-and-ui](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Похожие из своей БД актуальны при росте каталога.
- **Success Metrics**: Новичок в чужих карточках при inline_all.
- **Parent Alignment**: task.md similar.

### Technical

- **Primary Technical Objective**: apps/workers/similarity; embedding adapter; без LangGraph.
- **Implementation Scope**: Нет UI.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Cataloged games; optional reviews summaries; pgvector; daemon; Scheduler recompute events.

## Deliverables

Hybrid score, hash skip, modes, tests.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_embedding-hybrid-knn](Step_1_embedding-hybrid-knn/INDEX.md) |
| 2 | [Step_2_recompute-modes](Step_2_recompute-modes/INDEX.md) |
