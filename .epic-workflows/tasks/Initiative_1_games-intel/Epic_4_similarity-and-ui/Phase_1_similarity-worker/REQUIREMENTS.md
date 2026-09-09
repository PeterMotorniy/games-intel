# Similarity Worker Phase — Requirements

## Functional Requirements

- Consume game.cataloged, game.reviews.summarized (если recompute_on_reviews), similarity.recompute.requested.
- Канонический текст эмбеддинга: title, developer, publisher, genres, description, critic_summary, user_summary (если флаг); пустые поля пропускать, не «n/a».
- Hybrid score: vector, Jaccard platforms, Jaccard genres, release exp; веса из конфига; перенормировка.
- Нет эмбеддинга G → degraded, пустой список, не failed.
- Self запрещён. Top-K ORDER BY score DESC, slug tie-break.
- score в БД и CloudEvent — hybrid; score_vector nullable.

## Technical Requirements

- [similarity.md](../../../../../docs/architecture/workers/similarity.md) целиком.
- [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) SimilarityWorker.
- [data-model.md](../../../../../docs/architecture/database/data-model.md) similar_games, embedding columns.
- [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md) GameSimilarAssigned, SimilarityRecomputeRequested.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) similarity.*, embeddings.*.
- Sequential scan до hnsw_min_rows; HNSW отдельной миграцией не в этом шаге обязательно (порог 5000, демо без индекса).
- Идемпотентность similar и full recompute на час.

## Acceptance Criteria

- [x] Взаимные соседи после второго cataloged (inline_all).
- [x] Hash unchanged не зовёт fake embed.
- [x] Self отсутствует.
- [x] Нет соседей → completed пустой список.
- [x] Нет langchain в образе.

## Constraints

- Не агент. Не сайт.
- emit_assigned_for_all default false.
