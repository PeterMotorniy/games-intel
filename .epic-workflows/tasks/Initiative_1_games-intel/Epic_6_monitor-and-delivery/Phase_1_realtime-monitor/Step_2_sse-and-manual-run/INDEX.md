# SSE and Manual Run — Index

## Overview

GET /monitor/stream SSE; POST /runs outbox tick; UI монитор + кнопка. Родитель: [Phase_1_realtime-monitor](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Realtime и принудительный запуск без SSH.
- **Success Metrics**: 202; при стоящем курсоре replay той же listing page.
- **Parent Alignment**: доп. 2 кнопка.

### Technical

- **Primary Technical Objective**: SSE из API; outbox API producer source urn:...:api.
- **Implementation Scope**: Не CLI replay стадии.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- GET /monitor snapshot; Scheduler consume tick; web app.

## Deliverables

Stream endpoint; POST /runs; monitor page; a11y toast; browser verify.
