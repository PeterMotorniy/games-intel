# YouTube Adapter — Index

## Overview

In-process YouTubePort: search, transcript, optional audio clip. Родитель: [Phase_1_youtube-and-stt](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Самый популярный релевантный летсплей, не compilation.
- **Success Metrics**: items[0] после фильтров.
- **Parent Alignment**: task.md доп. 1 поиск.

### Technical

- **Primary Technical Objective**: packages/adapters/youtube.
- **Implementation Scope**: Не STT.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- youtube settings, timeout, api_key overlay.

## Deliverables

Port methods; unit filters; quota → AdapterError quota_exceeded.
