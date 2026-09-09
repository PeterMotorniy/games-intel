# Reviews Port — Requirements

## Functional Requirements

- Вход { slug, limit, max_chars } → ReviewBatch.
- Каждый сниппет урезан; HTML tags stripped.
- Критики и пользователи — разные методы/страницы по селекторам конфига.

## Technical Requirements

- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) get_critic_reviews / get_user_reviews.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) selectors reviews, limits.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) fixtures reviews.
- [agent-catalog.md](../../../../../../docs/architecture/agents/agent-catalog.md): агент порты не вызывает — DTO для воркера.
- Недоверенный контент: [AGENTS.md](../../../../../../AGENTS.md) § 5; [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md) принцип 6.

## Acceptance Criteria

- [x] Нет raw HTML в items.
- [x] limit соблюдён.
- [x] max_chars обрезает с truncated.
- [x] parse_error стабильный селекторов → ParseError.

## Constraints

- Агент не импортирует этот Port.
