# Typed Settings — Requirements

## Functional Requirements

- Загрузка: файл `APP_CONFIG_PATH` + overlay `GAMES_INTEL__SECTION__KEY` (вложенность `__`).
- Defaults как в таблицах configuration.md (tick_cron `0 * * * *`, default_limit 20, partitions.game_events 6, enable_auto_commit false, и т.д.).
- Процесс падает, если ключ неизвестен или обязательный секрет отсутствует для выбранного провайдера (правила stt/llm — валидаторы).

## Technical Requirements

Полный канон: [docs/architecture/core/configuration.md](../../../../../../docs/architecture/core/configuration.md).

Обязательно покрыть:

- `kafka.events.*` (все 10 имён type/topic).
- `kafka.consumer_groups.*` (шесть типов воркеров).
- `idempotency.key_template` = `{event_type}:{run_id}:{subject}:{stage}`.
- `scheduler.*` включая `tick_source`, advisory_lock_key, tick_dedup_window_seconds.
- Срезы `discovery|catalog|reviews|letsplay|similarity` (enabled, subscribe/publish, stage_name, instance_id, lease_seconds + специфика similarity весов/cron).
- `retry.*`, `adapters.metacritic.*` (включая markers/selectors keys, даже если селекторы заполнятся в Epic 2).
- `adapters.youtube.*`, `media.*`, `stt.*`, `llm.*`, `embeddings.*`, `langsmith.*`, `api.*`, `web.*`, `monitor.*`.

Тесты из configuration.md § Testing Strategy.

## Acceptance Criteria

- [x] Snapshot example-конфига совпадает с моделью (все ключи).
- [x] Unknown key → ValidationError при старте.
- [x] Overlay перекрывает yaml.
- [x] `enable_auto_commit` default false.
- [x] Документированный антипаттерн: реплики не имеют отдельного поля unique group — один `consumer_groups.catalog` на всех.

## Constraints

- Код приложений не вызывает `os.getenv`.
- Секреты (`DATABASE_URL`, api_key) только env overlay, не в git yaml с значениями.
