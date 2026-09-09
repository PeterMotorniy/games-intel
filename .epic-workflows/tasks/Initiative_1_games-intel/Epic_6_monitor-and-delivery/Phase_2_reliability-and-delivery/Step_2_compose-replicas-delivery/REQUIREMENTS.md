# Compose Replicas Delivery — Requirements

## Functional Requirements

Сервисы Compose:

- postgres 16 (vector, pg_trgm), kafka KRaft, topic init
- scrape-metacritic sidecar (internal)
- workers: scheduler, discovery, catalog (replicas≥2 демо опционально), reviews, letsplay, similarity
- api, web, volume covers
- один cron при scheduler.tick_source=external шлёт schedule_tick
- health/ready: postgres, kafka; sidecar /healthz; api /readyz

Реплики: одинаковый consumer_groups.*; instance_id из HOSTNAME; partitions.game_events ≥ N стадий игр.

README: конфиг, секреты env, как открыть UI, как ручной tick, что P0 (circuit, listing failed).

## Technical Requirements

- [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md) Deployment Considerations, раскладка, Quality Attributes observability.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) tick_source, partitions, secrets overlay.
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) Deployment, запрет разных group, sidecar не per-replica Chromium.
- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) nginx/caddy / и /api; не кэшировать monitor.
- [architecture-lifecycle](../../../../../../docs/architecture/index.md): Status Existing, Last Updated, index актуален, документы < 700 строк.
- [AGENTS.md](../../../../../../AGENTS.md) § 2 проверки перед завершением; § 10 git (коммит только по просьбе).
- [task.md](../../../../../../task.md) результат тестового.

## Acceptance Criteria

- [x] `compose up` поднимает контур; UI открывается.
- [x] Монитор показывает воркеры; две реплики catalog если заданы.
- [x] langchain отсутствует в images scheduler/discovery/catalog/similarity.
- [x] auto_migrate false в prod-профиле; local может применять миграции явно.
- [x] Architecture docs обновлены в том же изменении, что код расхождения.
- [x] Корневые проверки зелёные.

## Constraints

- Секреты не в git.
- Sidecar не публиковать в интернет.
- Не менять стек в конце «чтобы завелось» без правки architecture.
- JSONL переписки сдаётся отдельно, не как обязательный артефакт репозитория.
