# Cover Storage — Requirements

## Functional Requirements

- Ключ файла: metacritic_slug.
- Catalog после get_game пишет bytes если валидны; иначе cover_url=null, warning.
- games.cover_url в проекции = `{media.covers_url_prefix}/{slug}` т.е. `/api/v1/media/covers/{slug}`.
- games.cover_source_url — provenance.
- Скачивание предпочтительно в sidecar при get_game (тот же origin) или GET с таймаутом.

## Technical Requirements

- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) CoverStorage.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) § Обложки: битые байты не писать; API не проксирует произвольный URL.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) media.covers_dir, covers_url_prefix.
- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) GET media (контракт пути).
- Volume media/covers в compose (подключить полностью в Epic 6).

## Acceptance Criteria

- [x] Валидный jpeg/png сохраняется, повтор overwrite идемпотентен.
- [x] Пустые/битые bytes → нет файла, null url.
- [x] Путь не содержит path traversal от slug (sanitize).

## Constraints

- Не hotlink в UI.
- Не логировать bytes.
