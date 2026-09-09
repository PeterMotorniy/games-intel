# LetsPlay Pipeline Phase — Requirements

## Functional Requirements

Поток воркера:

1. search_letsplays → items[0]
2. нет роликов → no_video, без агентов
3. get_transcript; ok → текст
4. transcript_unavailable + STT on → get_audio + TranscriptionAgent; else transcript_unavailable
5. текст → LetsPlayAnalystAgent conclusion/highlights
6. persist + outbox GameLetsPlayAnalyzed

Обрезка transcript_max_chars **до** analyst. Статусы check constraint.

## Technical Requirements

- [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) LetsPlayWorker.
- [agent-catalog.md](../../../../../docs/architecture/agents/agent-catalog.md) Transcription + Analyst.
- [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md) GameLetsPlayAnalyzed.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) LetsPlay rows.
- [data-model.md](../../../../../docs/architecture/database/data-model.md) letsplay_* , GameLetsPlayRepository.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) letsplay.*, prompts.letsplay_analyst_path.
- Checkpoint thread_id для analyst/transcription; langchain в образе letsplay.

## Acceptance Criteria

- [x] no_video: 0 agent calls.
- [x] STT off + no captions: transcript_unavailable, no audio.
- [x] Quota: degraded quota_exceeded.
- [x] Analyst fail после лимита: stage failed, карточка без заключения.
- [x] Не затирает reviews/catalog.
- [x] Идемпотентность letsplay stage.

## Constraints

- Агенты без YouTubePort.
- Сырой транскрипт не в логи/монитор целиком.
