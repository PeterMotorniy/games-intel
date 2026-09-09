# Similarity and Catalog UI — Requirements

## Functional Requirements

- По `game.cataloged` (и при флаге по `game.reviews.summarized`) пересчитать top-K похожих из своей БД.
- Новая игра обновляет свой список и чужие (`inline_all` default до `inline_all_max_rows`).
- 0 соседей → пустой список, completed. Self запрещён.
- UI список: обложка, title, developer, агрегированный Metascore, чипы платформ; поиск, платформа, sort.
- UI карточка: поля ТЗ из catalog/reviews (letsplay — если колонки пустые, блок «ещё нет» / скрыть). Similar: клик по имени → `/games/{slug}`.
- Сортировка рейтинга: `max(metascore)` NULLS LAST; опционально userscore.

## Technical Requirements

- Алгоритм, веса, hash, режимы, HNSW-порог, события: [similarity.md](../../../../docs/architecture/workers/similarity.md).
- Embedding adapter (не агент). Пустые поля не подставлять как «n/a».
- Конфиг `similarity.*`, `embeddings.*` — [configuration.md](../../../../docs/architecture/core/configuration.md).
- События: `GameSimilarAssigned`, `SimilarGameRef.score` = hybrid, `SimilarityRecomputeRequested` — [event-contracts.md](../../../../docs/architecture/events/event-contracts.md).
- API: таблица эндпоинтов [web-ui.md](../../../../docs/architecture/frontend/web-ui.md). RFC 7807; 404 slug; 503 без БД.
- Поиск `pg_trgm` / ILIKE; фильтр `game_platforms`. Индексы — [data-model.md](../../../../docs/architecture/database/data-model.md).
- Клиент: React, TanStack Query, типы из OpenAPI, русский UI, `prefers-reduced-motion`, alt=title.
- Обложки: `GET /api/v1/media/covers/{slug}` — файл с volume, без прокси произвольного URL (SSRF).

## Acceptance Criteria

- [ ] Две игры — взаимные соседи после второго cataloged (inline_all).
- [ ] Третья вытесняет rank K; self отсутствует.
- [ ] Hash unchanged не дергает fake embed; top-K всё равно (incremental) / полная таблица (inline_all).
- [ ] Neighbors handler не пишет второе recompute (антишторм).
- [ ] Full recompute идемпотентен на `(process_date, hour)`.
- [ ] API фильтр/поиск/сортировка на фикстурах БД.
- [ ] UI: loading, empty («Игр пока нет»), error; клавиатура и фокус.
- [ ] Частичная карточка без reviews не 500.

## Constraints

- SimilarityWorker без langchain и без сайтов.
- HNSW только отдельной миграцией после `hnsw_min_rows` (на демо нет).
- UI не дублирует DTO руками.
- Query API не вызывает LLM.
