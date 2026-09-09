# Settings and Contracts — Requirements

## Functional Requirements

- Процесс читает yaml + env overlay; неизвестные ключи — ошибка старта.
- Реплики получают одинаковый `consumer_group` и разный `instance_id`.
- Каждое событие несёт `specversion`, `id`, `source`, `type`, `time`, `datacontenttype`, `dataschema`, `subject`, `idempotencykey`, `data`; расширения `runid`, `traceparent`.

## Technical Requirements

- Канон ключей: [configuration.md](../../../../../docs/architecture/core/configuration.md) — секции `app`, `kafka`, `idempotency`, `scheduler`, воркеры, `retry`, `database`, `adapters`, `media`, `stt`, `llm`, `embeddings`, `langsmith`, `api`, `web`, `monitor`.
- Конверт и каталог топиков: [event-contracts.md](../../../../../docs/architecture/events/event-contracts.md).
- Раскладка: `packages/settings`, `packages/contracts` — [system-architecture.md](../../../../../docs/architecture/core/system-architecture.md).
- JSON Schema и AsyncAPI 3 **генерируются** из Pydantic, не пишутся вторым руками.
- `topic_prefix` опционален для стенда.

## Acceptance Criteria

- [x] CI: ruff, mypy strict, pytest на settings/contracts.
- [x] Тест snapshot example yaml vs модель.
- [x] Тест required `idempotencykey`.
- [x] Генерация schema в CI не дрифтит (check).

## Constraints

- Секреты в example — пустые.
- Не хардкодить `0 * * * *`, `20`, имена топиков в будущих воркерах — запрет закладывается тестом settings.
