# LetsPlay Agents — Index

## Overview

TranscriptionAgent (SttPort wrap) и LetsPlayAnalystAgent (LangGraph structured conclusion/highlights, русский, промпт-файл). Родитель: [Phase_2_letsplay-pipeline](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Заключение по рассказу блогера на русском.
- **Success Metrics**: Structured I/O; STT optional.
- **Parent Alignment**: agent-catalog.

### Technical

- **Primary Technical Objective**: packages/agents/transcription, letsplay_analyst.
- **Implementation Scope**: Transcription без графа; Analyst со StateGraph.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- SttPort; llm settings; prompt path.

## Deliverables

Agents + fake tests; LangSmith projects; checkpoint analyst.
