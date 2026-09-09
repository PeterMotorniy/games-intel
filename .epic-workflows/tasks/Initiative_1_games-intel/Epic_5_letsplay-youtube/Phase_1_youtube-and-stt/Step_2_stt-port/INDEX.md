# STT Port — Index

## Overview

SttPort: faster-whisper default, Deepgram, AssemblyAI; один активный provider. Родитель: [Phase_1_youtube-and-stt](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Текст летсплея если нет субтитров (опционально, default выкл).
- **Success Metrics**: Демо без облачного ключа на whisper.
- **Parent Alignment**: agent-catalog Transcription.

### Technical

- **Primary Technical Objective**: packages/adapters/stt.
- **Implementation Scope**: Вызов из TranscriptionAgent, не отдельный Kafka демон.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- stt.* settings.

## Deliverables

Port + fake provider tests; timeout; fail mapping.
