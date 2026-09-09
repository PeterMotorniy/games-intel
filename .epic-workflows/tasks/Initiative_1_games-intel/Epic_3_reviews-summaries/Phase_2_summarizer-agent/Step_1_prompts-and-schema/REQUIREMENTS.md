# Prompts and Schema — Requirements

## Functional Requirements

- Вход: два списка ReviewSnippet (critic, user).
- Выход: critic/user ReviewSummary: likes[], dislikes[], summary str.
- Промпт явно требует JSON/schema и русский язык; внешний текст помечен как data.

## Technical Requirements

- [agent-catalog.md](../../../../../../docs/architecture/agents/agent-catalog.md) I/O.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) ReviewSummary; запрет regex.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) prompts.review_summarizer_path.
- [AGENTS.md](../../../../../../AGENTS.md) § 5: промпты файлы, structured, недоверенный контент.
- llm.model, temperature, max_tokens, timeout из settings, не литералы в агенте.

## Acceptance Criteria

- [x] Шаблон в git; версия в имени.
- [x] Модели Pydantic экспортируются для LangGraph structured output.
- [x] Нет URL Metacritic в промпте как команды.

## Constraints

- Не собирать промпт f-string из бизнес-кода воркера.
