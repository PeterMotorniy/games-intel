# LetsPlay Pipeline Phase — Index

## Overview

LetsPlayWorker + TranscriptionAgent + LetsPlayAnalystAgent. Родитель: [Epic_5_letsplay-youtube](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: В карточке ролик и заключение на русском.
- **Success Metrics**: Честные статусы no_video / transcript_unavailable / quota_exceeded.
- **Parent Alignment**: Доп. 1 полный контур.

### Technical

- **Primary Technical Objective**: apps/workers/letsplay + packages/agents/transcription + letsplay_analyst.
- **Implementation Scope**: UI блок уже умеет частичные данные.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- YouTube/STT ports; game.discovered; GameLetsPlayRepository; llm prompts.

## Deliverables

Worker flow 1–6; agents; tests.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_letsplay-worker](Step_1_letsplay-worker/INDEX.md) |
| 2 | [Step_2_letsplay-agents](Step_2_letsplay-agents/INDEX.md) |
