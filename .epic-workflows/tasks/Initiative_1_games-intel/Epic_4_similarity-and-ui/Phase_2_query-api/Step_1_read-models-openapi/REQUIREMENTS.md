# Read Models OpenAPI — Requirements

## Functional Requirements

- Read-модель игры: поля карточки ТЗ + genres + release_date + summaries + letsplay + similar items (slug, title, score, rank).
- Список: краткие поля + pagination meta.
- Problem details RFC 7807.

## Technical Requirements

- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) контракт.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) § AsyncAPI vs OpenAPI: UI язык проекций.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) колонки.
- page_size_default / page_size_max из settings.

## Acceptance Criteria

- [x] `/openapi.json` содержит games paths (после Step 2) и схемы.
- [x] Nullable letsplay/reviews допустимы.
- [x] score similar — hybrid float.

## Constraints

- Не экспортировать CloudEvents в UI.
- Не ручные TS-интерфейсы как source of truth.
