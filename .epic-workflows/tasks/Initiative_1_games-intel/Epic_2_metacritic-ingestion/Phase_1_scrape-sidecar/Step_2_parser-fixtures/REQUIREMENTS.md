# Parser Fixtures — Requirements

## Functional Requirements

- Маркеры `adapters.metacritic.markers.*`: контейнер, min карточек на непустой выдаче, заголовок секции.
- Нет маркера / селектор 0 при ожидаемой выдаче → parse_error.
- Часть карточек без slug — отбросить; если 0 и маркеры сомнительны → parse_error.
- get_game: title, cover_source_url, developer, publisher, description, video_url, platforms PlatformScore[], genres[], release_date.
- platform_code нормализован адаптером, не свободный текст.

## Technical Requirements

- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) § Fail-closed, § Golden fixtures.
- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) GameDetails, GameListing, PlatformScore.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) PlatformScore types.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) selectors.*, markers.*, new_releases_path, browse_path.
- Фикстуры: `tests/fixtures/metacritic/` — listing New Releases, browse page, card, reviews.
- Смена вёрстки = фикстура + селекторы.

## Acceptance Criteria

- [x] Unit без сети: фикстуры разбираются.
- [x] Пустой DOM → parse_error.
- [x] Маркеры на месте, 0 игр → пустой успех.
- [x] tbd scores → null.
- [x] genres и release_date снимаются с карточки (нужны Similarity).

## Constraints

- Селекторы не в воркерах.
- Не публиковать game.discovered из частично распознанного мусора (это Discovery, парсер не отдаёт битые slug).
