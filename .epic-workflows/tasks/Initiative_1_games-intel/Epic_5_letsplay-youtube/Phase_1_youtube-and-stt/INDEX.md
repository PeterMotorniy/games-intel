# YouTube and STT Phase — Index

## Overview

YouTubePort (поиск, субтитры, audio) и SttPort (faster-whisper / Deepgram / AssemblyAI). Родитель: [Epic_5_letsplay-youtube](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Найти релевантный популярный летсплей и получить текст.
- **Success Metrics**: Compilation отсечены; пустой поиск валиден.
- **Parent Alignment**: Доп. 1 сырьё.

### Technical

- **Primary Technical Objective**: packages/adapters/youtube и packages/adapters/stt.
- **Implementation Scope**: Нет Kafka worker (следующая фаза).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Settings youtube/stt/letsplay; contracts VideoHit, transcript DTO.

## Deliverables

Adapters + fake tests без сети.

## Child tasks

| # | Step |
|---|------|
| 1 | [Step_1_youtube-adapter](Step_1_youtube-adapter/INDEX.md) |
| 2 | [Step_2_stt-port](Step_2_stt-port/INDEX.md) |
