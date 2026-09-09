# Metacritic Games Intelligence — Index

## Overview

Сервис раз в час забирает с Metacritic до 20 ещё не обработанных в текущих календарных сутках игр, сохраняет карточку, резюме отзывов, похожие игры и анализ летсплея YouTube, отдаёт веб-каталог и realtime-монитор воркеров с кнопкой запуска.

Система — хореография автономных Kafka-демонов. LangChain/LangGraph — только там, где без модели нельзя (резюме отзывов, опциональный STT, заключение по транскрипту). Чат и эмбеддинги — OpenRouter; расшифровка аудио — OpenAI Whisper API. Источник правды по решению: [docs/architecture/core/system-architecture.md](../../../docs/architecture/core/system-architecture.md). Постановка: [task.md](../../../task.md).

## Goals

### Business / Product

- **Primary Business Objective**: Демонстрируемый сервис каталога игр с почасовым сбором с Metacritic, карточками, фильтрами и операторским монитором — обязательная часть ТЗ плюс обе дополнительные.
- **Business Impact**: Полный ответ на тестовое задание Skytec Games: репозиторий, живой сервис, трассировка работы с агентом.
- **User Value**: Пользователь видит актуальные игры, оценки, резюме отзывов, похожие тайтлы и (опционально) разбор летсплея; оператор видит пайплайн и может запустить прогон вручную.
- **Success Metrics**: 20 игр за run; смена суток сбрасывает выборку; UI: список, карточка, фильтр платформ, поиск, сортировка, similar; монитор SSE + POST tick.
- **Parent Alignment**: Корневая инициатива; родителя нет.

### Technical

- **Primary Technical Objective**: Реализовать стек из architecture: Python 3.12, FastAPI, Kafka, PostgreSQL 16 + pgvector, Playwright sidecar, React UI, агенты только в Reviews/LetsPlay.
- **Technical Impact**: Идемпотентные реплики, fail-closed скрейпинг, частичный успех стадий, восстановление с последнего устойчивого этапа.
- **Implementation Scope**: Весь репозиторий `apps/`, `packages/`, `infra/compose/` по раскладке в system-architecture. Вне скоупа: обход антибота «любой ценой», отдельный event store, retry одной игры из UI.
- **Quality Standards**: Контракты CloudEvents; unique `idempotency_key`; тесты без сети и без реального LLM; линт/типы/тесты зелёные.
- **Parent Alignment**: Техническая цель инициативы = канон [docs/architecture/index.md](../../../docs/architecture/index.md).

## Status

- [ ] Not Started
- [x] In Progress
- [ ] Completed
- [ ] Blocked

## Dependencies

- Зафиксированная архитектура в `docs/architecture/` (Status: Planned, 2026-09-07).
- Секреты стенда (YouTube Data API, Postgres, Kafka) — только env, не git.
- Доступ к Metacritic из scrape sidecar на стенде сдачи.

## Deliverables

1. Рабочий Compose-стенд: postgres, kafka, scrape sidecar, 6 воркеров (реплики допустимы), api, web, cron tick.
2. Обязательный пайплайн: Scheduler → Discovery → Catalog / Reviews / LetsPlay → Similarity.
3. Веб-каталог и карточка по [task.md](../../../task.md).
4. Доп. 1: летсплей YouTube + заключение.
5. Доп. 2: монитор реплик, circuit sidecar, кнопка запуска.
6. Ссылки на репозиторий и сервис; переписка с агентом.

## Child tasks

| # | Epic | Что закрывает |
|---|------|----------------|
| 1 | [Epic_1_platform-foundation](Epic_1_platform-foundation/INDEX.md) | Контракты, settings, БД, Kafka, каркас демона |
| 2 | [Epic_2_metacritic-ingestion](Epic_2_metacritic-ingestion/INDEX.md) | Sidecar, Scheduler, Discovery, Catalog, обложки |
| 3 | [Epic_3_reviews-summaries](Epic_3_reviews-summaries/INDEX.md) | Reviews worker + ReviewSummarizerAgent |
| 4 | [Epic_4_similarity-and-ui](Epic_4_similarity-and-ui/INDEX.md) | Hybrid similar + Query API + каталог UI |
| 5 | [Epic_5_letsplay-youtube](Epic_5_letsplay-youtube/INDEX.md) | YouTube, STT, LetsPlay worker и агенты |
| 6 | [Epic_6_monitor-and-delivery](Epic_6_monitor-and-delivery/INDEX.md) | SSE-монитор, recovery-тесты, Compose, сдача |

Порядок исполнения совпадает с Implementation Plan в [system-architecture.md](../../../docs/architecture/core/system-architecture.md) § Implementation Plan.

## Notes

- Воркеры не знают имён соседей; только Kafka + конфиг `kafka.events.*`.
- `os.environ` вне `packages/settings` запрещён.
- Расхождение кода и `docs/architecture/` — дефект в том же изменении.
