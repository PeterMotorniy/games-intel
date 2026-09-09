# Games Endpoints — Requirements

## Functional Requirements

- Список с q, platform, sort, order, page, page_size.
- Карточка 404 если нет slug.
- Platforms — distinct codes для фильтра.
- Media: file from volume; 404 нет файла; Cache-Control; sanitize slug.
- healthz liveness; readyz Postgres (+ optional Kafka).

## Technical Requirements

- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) table Method/Path.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) индексы, GREATEST/max metascore query.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) covers GET no SSRF.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) cors_origins.
- Слои: router → service → repository.

## Acceptance Criteria

- [x] Поиск находит по title trgm/ilike.
- [x] Фильтр platform исключает другие.
- [x] sort metascore NULLS LAST.
- [x] page_size > max → 400 problem+json.
- [x] 503 readyz без БД.

## Constraints

- Read-only домен игр.
- Не ходить в Kafka кроме будущего outbox tick.
