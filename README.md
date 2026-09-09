# Games Intel

Сервис каталога игр с Metacritic: почасовой ingest, карточки, резюме отзывов, похожие игры, летсплеи и монитор пайплайна.

Стек и границы слоёв: [docs/architecture](docs/architecture/index.md). Постановка: [task.md](task.md).

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Установка

```bash
uv sync
```

Конфиг: скопируйте `.env.example` в `.env` при необходимости. Секреты только в env, не в git. Пример дерева настроек — `config.example.yaml`.

```bash
cp .env.example .env
```

`APP_CONFIG_PATH` указывает на YAML. Overlay: `GAMES_INTEL__SECTION__KEY`.

## Проверки

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python -m games_intel.contracts.generate --check
uv run python -m games_intel.api.openapi --check
```

Перегенерировать JSON Schema и AsyncAPI 3 из Pydantic:

```bash
uv run python -m games_intel.contracts.generate
```

OpenAPI для веб-клиента (типы в `apps/web`):

```bash
uv run python -m games_intel.api.openapi
cd apps/web && npm run generate:api
```

Сгенерированные артефакты: `contracts/schemas/`, `contracts/asyncapi.yaml`, `apps/web/openapi.json`. Их нельзя править руками.

Веб-каталог:

```bash
cd apps/web
npm ci
npm test
npm run lint
npm run typecheck
npm run dev          # Vite + proxy на API :8000
npm run dev:stub     # Vite со stub Query API
```

## Раскладка

- `apps/` — API, воркеры, scrape sidecar, web
- `packages/settings` — типизированные settings
- `packages/contracts` — CloudEvents и payload-модели
- `packages/db` — PostgreSQL: Alembic-миграции и репозитории
- `packages/kafka` — CloudEvents producer/consumer, outbox relay, DaemonLoop
- `infra/compose/` — полный стенд: Postgres, Kafka, sidecar, воркеры, API, web, cron

## Стенд Docker Compose

Одна команда поднимает контур: Postgres 16 (pgvector/`pg_trgm`), Kafka KRaft, init топиков, явную миграцию, scrape sidecar, воркеры, API и UI.

```bash
cp .env.example .env
docker compose --env-file .env -f infra/compose/compose.yaml up -d --build
```

UI: [http://localhost:8080](http://localhost:8080) — каталог и [монитор](http://localhost:8080/monitor).

Query API за прокси: `/api/v1`. Sidecar Metacritic **не** публикуется наружу (только внутренняя сеть, `/healthz`).

`scheduler.tick_source=external`: отдельный контейнер `tick` шлёт `ingestion.schedule.tick` по `scheduler.tick_cron` (`0 * * * *`). Реплики Catalog (`deploy.replicas: 2` и сервис `catalog-replica`) — одна consumer group, разный `instance_id` из `HOSTNAME`.

LLM и эмбеддинги идут через **OpenRouter**: чат `google/gemini-2.5-flash-lite`, эмбеддинги `openai/text-embedding-3-small` (768-d). STT — OpenAI Whisper `whisper-1` (у OpenRouter нет transcriptions). Субтитры YouTube остаются основным путём расшифровки.

### Секреты (env, не git)

Скопируйте `.env.example` → `.env`. Без `GAMES_INTEL__LLM__API_KEY` (ключ OpenRouter) резюме, заключение летсплея и похожие игры деградируют. Без `GAMES_INTEL__STT__API_KEY` (ключ OpenAI) летсплей без субтитров деградирует. Без `ADAPTERS__YOUTUBE__API_KEY` стадия летсплеев деградирует.

| Переменная | Зачем |
|-----------|--------|
| `GAMES_INTEL__LLM__API_KEY` | ключ OpenRouter: чат и эмбеддинги |
| `GAMES_INTEL__STT__API_KEY` | ключ OpenAI только для Whisper |
| `GAMES_INTEL__ADAPTERS__YOUTUBE__API_KEY` | поиск летсплеев (YouTube Data API, не LLM) |
| `POSTGRES_PASSWORD` | пароль пользователя `games`; без него Compose не поднимет Postgres |
| `GAMES_INTEL__KAFKA__SASL_PASSWORD` | пароль пользователя `kafka` (SASL PLAIN); без него Compose не поднимет Kafka |

Overlay в Compose: `GAMES_INTEL__SECTION__KEY`. `database.auto_migrate=false`; миграции применяет сервис `migrate` явно.

Прод-профиль (тот же `auto_migrate=false`, `app.env=prod`):

```bash
docker compose --env-file .env -f infra/compose/compose.yaml -f infra/compose/compose.prod.yaml up -d
```

### Ручной tick

На мониторе кнопка **Run now** (POST `/api/v1/runs`, `trigger=manual`). Это новый tick, не retry конкретного slug. Если курсор суток стоит (listing fail / parse_error / circuit_open), повтор берёт **ту же** страницу listing.

Либо:

```bash
curl -X POST http://localhost:8080/api/v1/runs
```

### P0: что смотреть, если пайплайн молчит

- Монитор: `circuit_state=open`, рост `parse_error` за сутки, `ingestion_runs.status=failed` (listing не получен).
- Не крутить browse вперёд руками. Починить sidecar/селекторы/фикстуры или дождаться half-open, затем **Run now**.
- Не алертить каждый `degraded` летсплея (квота, нет ролика).

Health: Postgres `pg_isready`, Kafka broker API, sidecar `/healthz`, API `/readyz`.

### Локальная разработка без полного Compose

Только Postgres+Kafka:

```bash
docker compose --env-file .env -f infra/compose/compose.yaml up -d postgres kafka kafka-init
uv run python -m games_intel.db
```

Проверить топики (game-топики ≥ `kafka.partitions.game_events`, имена из `kafka.events.*`):

```bash
uv run python -m games_intel.kafka.topics --check
```

Локально: Postgres `localhost:5432` (user `games`, пароль из `POSTGRES_PASSWORD`), Kafka `localhost:9092` (SASL PLAIN, user `kafka`, пароль из `GAMES_INTEL__KAFKA__SASL_PASSWORD`).

- `GAMES_INTEL__DATABASE__URL=postgresql+asyncpg://games:${POSTGRES_PASSWORD}@localhost:5432/games_intel`
- `GAMES_INTEL__KAFKA__BOOTSTRAP_SERVERS=localhost:9092`

`database.url` берётся из settings (`DATABASE_URL` / `GAMES_INTEL__DATABASE__URL`).

Сдача по [task.md](task.md): ссылка на репозиторий, URL этого UI, JSONL переписки — отдельно, не в git.