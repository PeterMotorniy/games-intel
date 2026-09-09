# Reviews Daemon — Requirements

## Functional Requirements

- Параллель с Catalog по game.discovered.
- skip_agent_if_empty: degraded=true, counts 0, пустые ReviewSummary.
- Иначе ainvoke агента, persist critic_*/user_* json/text.
- Outbox GameReviewsSummarized (degraded flag, counts).
- Item status completed/degraded/failed; не трогать cover.

## Technical Requirements

- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) ReviewsWorker.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) GameReviewsSummarized.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) reviews columns, GameReviewsRepository.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) Reviews rows; изоляция стадий.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) § 2 демон с агентом.
- Реплики group reviews; stage reviews.
- Heartbeat instance_id.

## Acceptance Criteria

- [x] Empty: agent not called; degraded event.
- [x] Reviews не затирает cover_url.
- [x] Повтор события no-op.
- [x] Adapter Transient не коммитит offset.

## Constraints

- Воркер не парсит свободный текст модели.
- Агент не читает Kafka.
