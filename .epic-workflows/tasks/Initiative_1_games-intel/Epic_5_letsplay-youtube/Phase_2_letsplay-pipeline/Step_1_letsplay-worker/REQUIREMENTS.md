# LetsPlay Worker — Requirements

## Functional Requirements

- Consume game.discovered; produce game.letsplay.analyzed.
- Реализовать 6 шагов каталога; маппинг AdapterError.
- Писать letsplay_status, video_url/title/view_count, conclusion, highlights.
- STT/analyst только при условиях потока.
- item degraded vs failed по матрице ошибок.

## Technical Requirements

- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) LetsPlay поток.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) LetsPlay.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) group letsplay.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) агентный рестарт.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) payload fields.
- letsplay.search_max_results, stt_enabled, transcript_max_chars, max_video_duration_seconds.

## Acceptance Criteria

- [x] Матрица статусов на fake Port.
- [x] Повтор события no-op.
- [x] Transient YouTube timeout — retry offset.
- [x] Не вызывает analyst без текста.

## Constraints

- Воркер режет текст, не агент.
- Не знает Similarity/Catalog по имени.
