# Error and Recovery Tests — Requirements

## Functional Requirements

Покрыть минимум:

Error-handling:

- Poison CloudEvent → DLQ, следующее валидное ок.
- Listing 500 × N → run failed, курсор стоит.
- parse_error не двигает курсор, 0 discovered.
- Catalog 404 → item failed, другие стадии игры живут.
- Reviews empty → degraded, 0 LLM.
- LLM schema fail затем успех.
- LetsPlay quota → degraded quota_exceeded.
- circuit_open → Transient, listing не success.
- Две реплики / parallel handler → один persist.

Recovery:

- Kill после persist до offset → no duplicate domain.
- Unpublished outbox после restart публикуется.
- attempt_count не сбрасывается.
- Kill во время LLM → resume checkpoint (fake).
- Kill во время Catalog GET → повтор, возможен cache hit.
- UI tick не ретраит slug (контракт POST).

## Technical Requirements

- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) § Testing Strategy, матрица, диаграмма classify.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) § Testing Strategy, таблица «что уже есть».
- [replicas-and-idempotency.md](../../../../../../docs/architecture/workers/replicas-and-idempotency.md) § Testing Strategy (в т.ч. anti-test разных group документирован).
- [AGENTS.md](../../../../../../AGENTS.md) § 8 тесты детерминированы, без сети/LLM.
- Fake Port/LLM/clock.

## Acceptance Criteria

- [x] Все пункты выше — отдельные тесты или явно параметризованная матрица.
- [x] Падающий тест чинится причиной, не ослаблением.
- [x] Нет skip без описания.

## Constraints

- Не live сайты.
- Не реальный биллинг LLM.
