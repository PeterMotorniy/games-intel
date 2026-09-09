# Reliability and Delivery Phase — Requirements

## Functional Requirements

- Покрыть матрицу: schema poison, transient exhaust, 404 catalog, listing 500, parse_error курсор, empty reviews, quota letsplay, circuit_open.
- Recovery: kill persist-before-offset; unpublished outbox; attempt_count; agent checkpoint; listing crash.
- Compose: по контейнеру на воркер, replicas catalog, sidecar, api, web, postgres, kafka, covers volume, один cron если tick_source=external.
- Health postgres+kafka; sidecar /healthz.
- README: env, up, UI URL, ручной tick.

## Technical Requirements

- [error-handling.md](../../../../../docs/architecture/reliability/error-handling.md) Testing Strategy, изоляция, что не делаем.
- [recovery.md](../../../../../docs/architecture/reliability/recovery.md) Testing Strategy, runbook.
- [system-architecture.md](../../../../../docs/architecture/core/system-architecture.md) Deployment, Implementation Plan п.6, Quality Attributes.
- [replicas-and-idempotency.md](../../../../../docs/architecture/workers/replicas-and-idempotency.md) Compose deploy.replicas, HOSTNAME instance_id, запрет разных group.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) tick_source external канон.
- Architecture lifecycle: обновить Status/Last Updated где реализовано — [docs/architecture](../../../../../docs/architecture/index.md).
- [task.md](../../../../../task.md) результат: repo, service URL, JSONL переписки (не секрет в git).

## Acceptance Criteria

- [x] Перечисленные тесты без сети/реального LLM.
- [x] compose поднимает весь контур.
- [x] Реплики одного group, разный instance_id в мониторе.
- [x] ruff/mypy/pytest (и frontend lint/test) зелёные.
- [x] Docs не расходятся с кодом в том же изменении.

## Constraints

- Не зеленть тесты skip/xfail без причины.
- Не коммитить секреты и agent transcripts с ключами.
