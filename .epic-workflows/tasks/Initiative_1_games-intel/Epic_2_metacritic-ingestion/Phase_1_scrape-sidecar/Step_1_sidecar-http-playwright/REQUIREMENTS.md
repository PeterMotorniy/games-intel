# Sidecar HTTP Playwright — Requirements

## Functional Requirements

- Эндпоинты sidecar соответствуют методам Port: listing new releases, browse page, get game, canary (и заготовка reviews).
- Клиент воркера: `adapters.metacritic.sidecar_base_url`, timeout.
- min_delay_ms между навигациями + jitter_ratio.
- headless, user_agent, locale из конфига.

## Technical Requirements

- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) Runtime table, MetacriticPort interfaces, «Реплики не поднимают свой Chromium».
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) sidecar_base_url, mode, pool_size, min_delay_ms, timeout_seconds, headless, user_agent, base_url, paths, browse_page_query_param.
- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) § Вежливость и антишторм.
- httpx + Pydantic; Playwright в image sidecar.

## Acceptance Criteria

- [x] mode=in_process подменяет реализацию в тестах без Playwright.
- [x] mode=sidecar сериализует те же DTO.
- [x] Таймаут каждого внешнего вызова.
- [x] Sidecar не слушает public без явного портопроброса (compose internal).

## Constraints

- Не парсить HTML в воркере.
- Не параллелить десятки вкладок.
