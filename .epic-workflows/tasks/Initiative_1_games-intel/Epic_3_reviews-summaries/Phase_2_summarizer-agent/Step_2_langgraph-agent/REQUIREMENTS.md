# LangGraph Review Agent — Requirements

## Functional Requirements

- Граф: structured LLM nodes; параллель critic/user допустима; без tools.
- Timeout/5xx модели — retry агента; schema — llm_structure_retries.
- thread_id `{run_id}:{slug}:{agent_name}` < 255.
- LangSmith down — агент работает, tracing warning.

## Technical Requirements

- [agent-catalog.md](../../../../../../docs/architecture/agents/agent-catalog.md) ReviewSummarizer, Technical Details.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) ValidationError LLM, RetryPolicy only model node.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) § 2 PostgresSaver; langgraph-checkpoint-postgres не в чистых демонах.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) llm.*, langsmith.*, retry.llm_structure_retries.
- Testing: fake LLM; повтор invoke без Kafka.

## Acceptance Criteria

- [x] Structured output валиден.
- [x] Kill-before-persist сценарий: checkpoint возвращает готовый output (fake saver).
- [x] Reviews image содержит langchain; scheduler image — нет (проверка Dockerfile/pyproject).

## Constraints

- Агент не знает Kafka/URL сайтов.
- Не ставить checkpoint на Catalog.
