# Recompute Modes — Requirements

## Functional Requirements

- inline_all (default, N < inline_all_max_rows 2000): upsert embed G; пересчитать similar_games для всех с эмбеддингом в одной транзакции; outbox assigned только на G если emit_assigned_for_all false.
- incremental: top-K G; candidates reverse_candidate_limit + текущие соседи; outbox recompute scope=neighbors; handler neighbors без повторного fan-out.
- scope=all: полная пересборка; unique на час process_date+hour.
- scope=game: одна игра без fan-out.
- reviews.summarized: ignore+commit если не recompute_on_reviews.
- Hash не изменился: embed skip; top-K всё равно (incremental) / полная таблица (inline_all).

## Technical Requirements

- [similarity.md](../../../../../../docs/architecture/workers/similarity.md) § Режимы, § События, § Идемпотентность, mermaid.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) SimilarityRecomputeRequested fields reason/scope.
- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) consume list.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) group similarity; full recompute control partitions.
- Testing Strategy similarity.md.

## Acceptance Criteria

- [x] Две игры взаимные соседи inline_all.
- [x] Третья вытесняет K.
- [x] Neighbors handler не пишет второе recompute.
- [x] Повтор cron того же часа no-op.
- [x] 0 соседей completed.
- [x] 1 другая игра K=1.

## Constraints

- UI tick не обязан слать full recompute.
- Не каскадить neighbors.
