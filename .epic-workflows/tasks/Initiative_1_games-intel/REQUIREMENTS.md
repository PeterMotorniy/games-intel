# Metacritic Games Intelligence — Requirements

## Functional Requirements

Обязательная часть [task.md](../../../task.md):

- Раз в час (cron из конфига `scheduler.tick_cron`, default `0 * * * *`) сервис забирает до `scheduler.default_limit` (20) игр, которых нет в `daily_processed_slugs` за `process_date`.
- Первый прогон суток: New Releases `https://www.metacritic.com/game/`. Далее browse newest `https://www.metacritic.com/browse/game/all/all/all-time/new/` постранично. Смена суток сбрасывает browse-курсор. Timezone: `app.process_timezone` (default UTC).
- Карточка: название, локальная обложка, платформы + Metascore + Userscore, разработчик, описание, ссылка на видео.
- Резюме отзывов отдельно для критиков и пользователей («что нравится / нет»); можно обновлять при повторных обходах той же игры в другой день.
- UI: список, карточка, фильтр платформ, поиск по названию, сортировка по рейтингу.
- Похожие игры только из своей БД; клик открывает карточку; self запрещён.

Дополнительно:

1. Самый популярный релевантный летсплей YouTube, текст (субтитры или STT), заключение на русском, ссылка на ролик.
2. Realtime-монитор воркеров/реплик, счётчики, circuit sidecar, кнопка принудительного запуска (новый tick, не retry slug).

Детализация потока: [docs/architecture/core/system-architecture.md](../../../docs/architecture/core/system-architecture.md) § «Поток за сутки», § «Выборка Metacritic».

## Technical Requirements

- Стек: Python 3.12 + uv, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Kafka 3.x KRaft, PostgreSQL 16 + pgvector + pg_trgm, Playwright sidecar, React + TS + Vite + TanStack Query, Docker Compose. См. system-architecture § Technology Stack.
- Раскладка репозитория — таблица в system-architecture § «Репозиторная раскладка».
- Зависимости: transport → services → repositories. LLM только `packages/agents`. Scheduler/Discovery/Catalog/Similarity **не** зависят от langchain.
- Конфигурация: полное дерево [docs/architecture/core/configuration.md](../../../docs/architecture/core/configuration.md). Имена топиков, group id, cron, лимит 20, селекторы — не литералы в коде.
- События: CloudEvents 1.0 + обязательный `idempotencykey`. [docs/architecture/events/event-contracts.md](../../../docs/architecture/events/event-contracts.md).
- Реплики: одна consumer group на тип воркера; идемпотентность в PostgreSQL. [docs/architecture/workers/replicas-and-idempotency.md](../../../docs/architecture/workers/replicas-and-idempotency.md).
- Ошибки и recovery: [docs/architecture/reliability/error-handling.md](../../../docs/architecture/reliability/error-handling.md), [docs/architecture/reliability/recovery.md](../../../docs/architecture/reliability/recovery.md).
- Скрейпинг fail-closed: [docs/architecture/integrations/scraping-resilience.md](../../../docs/architecture/integrations/scraping-resilience.md).
- Similarity hybrid + reverse refresh: [docs/architecture/workers/similarity.md](../../../docs/architecture/workers/similarity.md).
- UI: [docs/architecture/frontend/web-ui.md](../../../docs/architecture/frontend/web-ui.md).

## Acceptance Criteria

- [ ] Часовой tick (или ручной POST `/runs`) создаёт run и обрабатывает до 20 новых за сутки игр.
- [ ] Первый run дня — New Releases; следующие — очередная browse-страница; listing fail не двигает курсор.
- [ ] Карточка в UI содержит поля из обязательной части ТЗ; неполная гидратация (нет отзывов/летсплея) не даёт 500.
- [ ] Фильтр платформ, поиск по title, сортировка по `max(metascore)` NULLS LAST работают.
- [ ] Похожие игры из БД, взаимно согласованы при `inline_all`; клик ведёт на карточку.
- [ ] Резюме критиков и пользователей на русском; пустые отзывы → `degraded`, агент не вызывается.
- [ ] Летсплей: ролик + заключение или честный статус `no_video` / `transcript_unavailable` / `quota_exceeded`.
- [ ] Монитор показывает реплики по `instance_id`, counts по stage/status, circuit; кнопка даёт 202 и tick.
- [ ] Две реплики Catalog на одном событии: один persist, один no-op.
- [ ] Unit/интеграционные тесты без сети и без реального LLM; миграции с нуля; проверки репозитория зелёные.

## Constraints

- Не менять стек, схему или контракт API без правки architecture docs в том же изменении.
- Секреты только env; `.env.example` / `config.example.yaml` с пустыми значениями.
- Агенты не читают Kafka и не ходят на Metacritic/YouTube.
- Query API не вызывает LLM и не дергает воркеров по RPC — только outbox tick.
- Ручной запуск ≠ retry конкретной игры ([recovery.md](../../../docs/architecture/reliability/recovery.md) § 7).
- Документ architecture ≤ 700 строк; задачи не дублируют канон, а ссылаются на него.
