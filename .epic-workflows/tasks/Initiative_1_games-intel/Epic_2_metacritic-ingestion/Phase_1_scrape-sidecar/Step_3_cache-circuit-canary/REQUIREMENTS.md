# Cache Circuit Canary — Requirements

## Functional Requirements

- Кеш PK `url_hash`; TTL `cache_ttl_seconds` default 3600; Transient retry читает свежий кеш.
- Circuit: fail_threshold default 3 parse_error подряд; open_seconds 600; open → методы возвращают circuit_open.
- Half-open: один canary или listing; успех closed, parse_error снова open.
- Canary: `canary_enabled`, `canary_slug`; неуспех → не listing; canary не пишет daily_processed_slugs (это Discovery).
- Зеркало состояния в `adapter_health` для API.

## Technical Requirements

- [scraping-resilience.md](../../../../../../docs/architecture/integrations/scraping-resilience.md) § Page cache, Circuit, Canary, монитор поля.
- [data-model.md](../../../../../../docs/architecture/database/data-model.md) external_page_cache, adapter_health.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) circuit_open → Transient; parse_error P0.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) canary_*, circuit_*, cache_ttl.
- Инвалидация кеша по TTL; ручной POST оператора вне MVP UI.

## Acceptance Criteria

- [x] Кеш hit без сети.
- [x] Circuit открывается после N ошибок на fake.
- [x] canary fail не вызывает listing в интеграционном тесте Discovery-заглушки или sidecar-флаге.
- [x] adapter_health.circuit_state обновляется.

## Constraints

- Canary не отдельный Kafka-воркер.
- Не алертить логикой sidecar каждый degraded (алерты — ops Epic 6).
