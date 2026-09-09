# Reviews Summaries — Requirements

## Functional Requirements

- По `game.discovered` скачать батчи отзывов критиков и пользователей (лимиты `reviews.critic_limit`, `user_limit`, `max_chars`).
- Пустые батчи → `degraded=true`, пустые summary, агент **не** вызывается (`reviews.skip_agent_if_empty`).
- Иначе агент возвращает `critic: ReviewSummary`, `user: ReviewSummary` (likes, dislikes, summary) на русском.
- Обновление среза reviews не затирает catalog/letsplay колонки.
- Стадия failed после лимита LLM не валит catalog/letsplay той же игры.

## Technical Requirements

- Поток ReviewsWorker: [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md) § ReviewsWorker.
- Port: [adapters.md](../../../../docs/architecture/integrations/adapters.md) `get_critic_reviews` / `get_user_reviews` → `ReviewBatch`.
- Агент: [agent-catalog.md](../../../../docs/architecture/agents/agent-catalog.md) ReviewSummarizerAgent. Граф: один/два node structured output, без tools, без Kafka.
- Контракт: [event-contracts.md](../../../../docs/architecture/events/event-contracts.md) `ReviewSummary`, `GameReviewsSummarized`.
- Промпт: файл `prompts.review_summarizer_path`. Недоверенный текст — data.
- Checkpoint: `thread_id = {run_id}:{slug}:{agent_name}`, длина < 255. [recovery.md](../../../../docs/architecture/reliability/recovery.md) § 2.
- Retry: адаптер — демон; LLM 5xx/timeout и ValidationError схемы — агент до `retry.llm_structure_retries`. [error-handling.md](../../../../docs/architecture/reliability/error-handling.md).
- Репозиторий: `GameReviewsRepository` — [data-model.md](../../../../docs/architecture/database/data-model.md).
- Конфиг: `reviews.*`, `llm.*`, `langsmith.*` — [configuration.md](../../../../docs/architecture/core/configuration.md).

## Acceptance Criteria

- [x] HTML не попадает в агент и не пишется в БД.
- [x] Пустые отзывы: item `degraded`, 0 вызовов fake LLM.
- [x] Structured output не парсится regex; повтор invoke при schema fail затем успех.
- [x] Reviews update не затирает `cover_url`.
- [x] Kill после успешного LLM до persist: resume из PostgresSaver без второго биллинга (тест fake saver).
- [x] Идемпотентный повтор `game.discovered`: один reviews-срез.
- [x] LangSmith tracing опционален; падение LangSmith не валит агента.

## Constraints

- Агент не вызывает MetacriticPort.
- Воркер не собирает промпт строками в коде.
- langchain только в пакете агента и образе Reviews.
