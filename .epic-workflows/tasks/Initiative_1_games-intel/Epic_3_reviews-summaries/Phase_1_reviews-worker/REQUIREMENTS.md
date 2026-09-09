# Reviews Worker Phase — Requirements

## Functional Requirements

- Скачать critic и user reviews с лимитами и max_chars.
- ReviewBatch { items: ReviewSnippet[], truncated }; HTML отброшен.
- Пустые items → degraded, пустые summary, агент не звать.
- Иначе передать сниппеты в ReviewSummarizerAgent (Phase 2).
- Persist reviews columns + GameReviewsSummarized.

## Technical Requirements

- [adapters.md](../../../../../docs/architecture/integrations/adapters.md) review methods.
- [worker-catalog.md](../../../../../docs/architecture/workers/worker-catalog.md) Reviews поток 1–4.
- [scraping-resilience.md](../../../../../docs/architecture/integrations/scraping-resilience.md) фикстуры reviews.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) reviews.critic_limit, user_limit, max_chars, skip_agent_if_empty.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) Reviews timeout vs empty.

## Acceptance Criteria

- [x] Фикстуры reviews без сети.
- [x] truncated=true если обрезали.
- [x] Empty → 0 agent calls.
- [x] Adapter timeout → Transient.

## Constraints

- Воркер не собирает промпт.
- Недоверенный текст только data.
