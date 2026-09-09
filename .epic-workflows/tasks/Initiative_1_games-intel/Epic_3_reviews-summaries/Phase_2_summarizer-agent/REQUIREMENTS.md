# Summarizer Agent Phase — Requirements

## Functional Requirements

- ainvoke(ReviewSummarizerInput) → ReviewSummarizerOutput { critic, user: ReviewSummary }.
- Язык резюме: русский.
- Пустой вход воркер не передаёт.
- Невалидная схема — retry.llm_structure_retries; затем воркер failed.

## Technical Requirements

- [agent-catalog.md](../../../../../docs/architecture/agents/agent-catalog.md) ReviewSummarizerAgent.
- Промпт path: configuration prompts.review_summarizer_path.
- Structured output = контракт event-contracts ReviewSummary.
- LangSmith project `{prefix}-review-summarizer`; tracing degrade если LangSmith down ([recovery.md](../../../../../docs/architecture/reliability/recovery.md) § 6).
- PostgresSaver только этот subgraph; thread_id `{run_id}:{slug}:review_summarizer`.
- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) политика агентов.
- langchain только в этом пакете + reviews image.

## Acceptance Criteria

- [x] Fixture snippets → валидный Pydantic с fake LLM.
- [x] Schema fail then success.
- [x] Повтор invoke не проверяет Kafka.
- [x] Нет tools/сайтов в графе.

## Constraints

- Вход как data, не инструкции со страницы.
- Не отправлять сырые большие документы — уже урезанные сниппеты.
