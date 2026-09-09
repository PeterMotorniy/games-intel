# Embedding Hybrid kNN — Requirements

## Functional Requirements

- embedding_input_hash = SHA-256(каноническая строка + embeddings.model + vector_dim).
- Cosine в [0,1]; нет вектора пары → вне kNN.
- platforms Jaccard кодов; genres Jaccard; release exp(-|days|/tau) tau default 365; нет даты → 0.
- Веса default 0.70/0.15/0.10/0.05; нулевые сигналы перенормировка.
- K = similarity.k default 5.

## Technical Requirements

- [similarity.md](../../../../../../docs/architecture/workers/similarity.md) § Вход эмбеддинга, § Hybrid score.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) w_*, release_tau_days, embeddings.vector_dim.
- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) similarity — embedding adapter.
- Смена модели → hash mismatch → rebuild (не обязательно миграция в этом шаге).
- pgvector `<=>` sequential.

## Acceptance Criteria

- [x] Одинаковый вход → тот же hash, skip API.
- [x] Пустые поля не вставляют n/a в текст.
- [x] Нет эмбеддинга → degraded пустой список.
- [x] Tie-break slug стабилен.

## Constraints

- Embedding не LangGraph агент.
- Без сети в unit (fake HTTP).
