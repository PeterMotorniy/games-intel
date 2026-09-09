# Query API Phase — Requirements

## Functional Requirements

- GET /api/v1/games: q, platform, sort=metascore|userscore|title|updated, order, page, page_size.
- GET /api/v1/games/{slug}: карточка + platforms + genres + release_date + summaries + letsplay + similar.
- GET /platforms, GET /media/covers/{slug}, GET /healthz, GET /readyz (Postgres, опционально Kafka).
- Сортировка max(metascore) NULLS LAST. Поиск ILIKE/trgm. Фильтр наличие platform_code.
- Ошибки problem+json. 404 slug. 503 БД нет.
- Частичная гидратация нормальна.

## Technical Requirements

- [web-ui.md](../../../../../docs/architecture/frontend/web-ui.md) § Query API.
- [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md) OpenAPI из доменных read-моделей, не CloudEvents.
- [data-model.md](../../../../../docs/architecture/database/data-model.md) индексы поиска.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) api.host/port/cors/page_size_*.
- [AGENTS.md](../../../../../AGENTS.md) § 3: роутер валидирует, сервис читает, репозиторий SQL.
- Covers: Cache-Control свой; не SSRF.

## Acceptance Criteria

- [x] Тесты фильтров/сортировки/пагинации.
- [x] OpenAPI генерируется.
- [x] ready 503 без postgres.
- [x] Cover 404 если файла нет.
- [x] Self нет в similar (гарантия БД + API не добавляет).

## Constraints

- API не вызывает LLM и воркеров по имени.
- Типы полей игр совпадают с catalog/reviews/letsplay схемами.
