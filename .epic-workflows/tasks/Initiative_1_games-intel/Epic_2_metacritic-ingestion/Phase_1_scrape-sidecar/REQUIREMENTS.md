# Scrape Sidecar — Requirements

## Functional Requirements

- Port: `list_new_releases`, `list_browse_page`, `get_game`, `canary_parse` (reviews — контракт, реализация минимум stub с тем же AdapterError).
- Пустой listing без маркеров → parse_error, не успех.
- Маркеры на месте, 0 игр → успех пустой страницы.
- 404 карточки → not_found. 403/timeout → unavailable/timeout.
- Единый min_delay_ms, pool_size, user_agent, headless из конфига.

## Technical Requirements

- [adapters.md](../../../../../docs/architecture/integrations/adapters.md) MetacriticPort + Runtime sidecar.
- [scraping-resilience.md](../../../../../docs/architecture/integrations/scraping-resilience.md) целиком.
- Селекторы/маркеры/пути: [configuration.md](../../../../../docs/architecture/core/configuration.md) `adapters.metacritic.*`.
- URL только из `base_url` + paths внутри адаптера.
- AdapterError codes: not_found|timeout|rate_limited|parse_error|quota_exceeded|unavailable|circuit_open.

## Acceptance Criteria

- [x] Golden HTML → DTO в CI.
- [x] Пустой DOM → parse_error.
- [x] Кеш hit без сети на retry.
- [x] Circuit open после N parse_error.
- [x] /healthz sidecar.
- [x] Cover bytes в get_game или отдельный GET; битые не отдавать как успех файла.

## Constraints

- Воркеры не содержат селекторов.
- Не обход защиты «любой ценой».
- HTML не уходит в Kafka.
