# Catalog Worker — Requirements

## Functional Requirements

- Consume kafka.events.game_discovered; group catalog; stage_name cataloged.
- Входящий idempotency_key discovered; исходящий `{cataloged_type}:{run_id}:{slug}:cataloged`.
- Persist: catalog columns + replace platforms; item completed/failed/degraded-fields.
- Produce GameCataloged со всеми полями контракта (cover_url локальный путь/URL).
- Нет видео / нет developer — warning, completed (empty_video_ok).
- 404 NotFoundError: item failed, commit, без DLQ обязательного.
- Transient listing/get timeout: retry по политике демона.

## Technical Requirements

- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) CatalogWorker.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) GameCataloged.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) пример ключей Catalog.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) Catalog 404 vs degrade полей.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) GameCatalogRepository.
- Scaling: partitions.game_events >= replicas.
- source urn:...:worker:catalog.

## Acceptance Criteria

- [x] Срез не затирает critic_summary.
- [x] Две реплики — один persist.
- [x] 404 не ретраится.
- [x] Similarity ещё нет — событие cataloged всё равно в outbox.

## Constraints

- Нет langchain.
- Нет селекторов в воркере.
