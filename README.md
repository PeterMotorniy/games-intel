# Games Intel

Hourly Metacritic game catalog: scrape new releases, persist cards, summarize critic and user reviews, find similar titles already in the database, attach a YouTube let's-play conclusion, and expose a web UI plus a live pipeline monitor.

Architecture, event flow, data model, and reliability: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).  
LLM chat log for this project: [llm-transcripts.jsonl](llm-transcripts.jsonl).

## What it does

Once an hour (or on **Run now** in the UI) the service:

1. Takes up to 20 games that it has not processed yet **today**.
2. First tick of the calendar day: [New Releases](https://www.metacritic.com/game/). Later ticks: the next page of [browse / newest](https://www.metacritic.com/browse/game/all/all/all-time/new/).
3. Stores title, cover, platforms with Metascore and Userscore, developer, description, and trailer URL.
4. Summarizes critic reviews and user reviews separately (likes / dislikes / short summary).
5. Picks similar games **from its own catalog** and shows them on the card.
6. Searches YouTube for a popular let's play, transcribes the commentary, and adds a conclusion with a link to the video.

The UI:

- Game list with search, platform filter, and score sort
- Game card with full fields, review blocks, similar titles, and let's play
- Monitor: per-run DAG, worker progress, **Run now**

Partial cards are normal. Reviews, similarity, and let's play fill in after the catalog stage.

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.12, [uv](https://docs.astral.sh/uv/) workspace |
| API | FastAPI, OpenAPI-generated TypeScript client |
| UI | React 19, Vite, TanStack Query |
| Bus | Kafka 3.8 KRaft, CloudEvents 1.0 |
| Store | PostgreSQL 16, pgvector, `pg_trgm` |
| Scrape | Playwright sidecar (HTTP JSON) |
| LLM / embeddings | OpenRouter (`google/gemini-2.5-flash-lite`, `openai/text-embedding-3-small`) |
| STT | OpenAI Whisper `whisper-1` translations (English text) |
| YouTube | yt-dlp InnerTube (search, captions, audio). No Google API key. |
| Agents | LangChain / LangGraph **only** inside Reviews and LetsPlay workers |

Workers are autonomous Kafka daemons. They do not call each other. LangGraph is not used for scraping, scheduling, catalog, or similarity.

## Requirements

- Docker Engine with Compose v2 (full stack)
- For checks without Docker: Python 3.12, uv, Node.js 20+

## Run locally (Docker Compose)

Copy env, set passwords and API keys, then start everything:

```bash
cp .env.example .env
# Fill POSTGRES_PASSWORD, GAMES_INTEL__KAFKA__SASL_PASSWORD
# Optional: GAMES_INTEL__LLM__API_KEY (OpenRouter), GAMES_INTEL__STT__API_KEY (OpenAI Whisper)

docker compose --env-file .env -f infra/compose/compose.yaml up -d --build
```

- UI: [http://localhost:8080](http://localhost:8080)
- Monitor: [http://localhost:8080/monitor](http://localhost:8080/monitor)
- Query API (behind nginx): `/api/v1`
- Metacritic sidecar is **internal only** (`/healthz`)

The first ingest of the day is scheduled by the `tick` container (`scheduler.tick_cron`, default hourly). You can also click **Run now** or:

```bash
curl -X POST http://localhost:8080/api/v1/runs
```

`scheduler.tick_source=external`: a single `tick` service publishes `ingestion.schedule.tick`. Catalog runs two replicas (`catalog` and `catalog-replica`) in one consumer group; `instance_id` comes from `HOSTNAME`.

Migrations run as an explicit `migrate` service (`database.auto_migrate=false`). Postgres and Kafka stay up across Docker Desktop restarts (`restart: unless-stopped`).

### Secrets

Never commit `.env`. Overlay keys use `GAMES_INTEL__SECTION__KEY`.

| Variable | Purpose |
|----------|---------|
| `POSTGRES_PASSWORD` | Postgres user `games` (required for Compose) |
| `GAMES_INTEL__KAFKA__SASL_PASSWORD` | Kafka SASL PLAIN user `kafka` (required for Compose) |
| `GAMES_INTEL__LLM__API_KEY` | OpenRouter: review summaries, let's-play conclusion, embeddings |
| `GAMES_INTEL__STT__API_KEY` | OpenAI Whisper when YouTube has no English captions |

Without the LLM key, summaries, let's-play conclusions, and similar-game vectors degrade. Without the STT key, let's play without captions degrades. The catalog still works.

Canonical non-secret settings: [`config.example.yaml`](config.example.yaml). Path: `APP_CONFIG_PATH`.

### Public HTTPS URL (optional)

From the repo root, with the stack already on port 8080:

```powershell
.\start-tunnel.ps1
```

The script prints `https://….lhr.life`. Leave that window open. Ctrl+C stops the tunnel. The URL changes each run.

### Production overlay

Same stack, `app.env=prod`, still no auto-migrate:

```bash
docker compose --env-file .env -f infra/compose/compose.yaml -f infra/compose/compose.prod.yaml up -d
```

### If the pipeline is silent

- Monitor: `circuit_state=open`, `parse_error` growing, `ingestion_runs.status=failed` (listing not fetched).
- Do not advance the browse cursor by hand. Fix sidecar / selectors / fixtures, or wait for half-open, then **Run now**.
- Let's-play `degraded` (quota, no video) is expected and is not a P0.

Health: Postgres `pg_isready`, Kafka broker API, sidecar `/healthz`, API `/readyz`.

## Run checks (CI locally)

Python workspace from the repo root:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python -m games_intel.contracts.generate --check
uv run python -m games_intel.api.openapi --check
```

Regenerate JSON Schema / AsyncAPI from Pydantic (do not edit generated files by hand):

```bash
uv run python -m games_intel.contracts.generate
uv run python -m games_intel.api.openapi
cd apps/web && npm run generate:api
```

Frontend:

```bash
cd apps/web
npm ci
npm test
npm run lint
npm run typecheck
npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs the same Python and web jobs, plus `docker compose … config` for the prod overlay.

`npm run dev` proxies Vite to the API on `:8000`. `npm run dev:stub` uses in-memory catalog data without the API.

## Develop without the full Compose stack

Postgres + Kafka only:

```bash
cp .env.example .env
docker compose --env-file .env -f infra/compose/compose.yaml up -d postgres kafka kafka-init
uv run python -m games_intel.db
uv run python -m games_intel.kafka.topics --check
```

Local ports:

- Postgres `localhost:5432` — user `games`, password `POSTGRES_PASSWORD`
- Kafka `localhost:9092` — SASL PLAIN, user `kafka`, password `GAMES_INTEL__KAFKA__SASL_PASSWORD`

```text
GAMES_INTEL__DATABASE__URL=postgresql+asyncpg://games:${POSTGRES_PASSWORD}@localhost:5432/games_intel
GAMES_INTEL__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
```

## Layout

```text
apps/api/                 Query API (FastAPI)
apps/web/                 Catalog + monitor UI
apps/workers/             Kafka daemons (scheduler, discovery, catalog, reviews, letsplay, similarity)
apps/scrape/metacritic/   Playwright HTTP sidecar
packages/adapters/        Typed ports (Metacritic, YouTube, media, STT, embeddings)
packages/agents/          LLM/STT procedures (no Kafka, no site HTTP)
packages/contracts/       CloudEvents + Pydantic models
packages/db/              Alembic + repositories
packages/kafka/           Consumer loop, outbox relay
packages/settings/        Typed YAML + env overlay
contracts/                Generated JSON Schema and AsyncAPI
infra/compose/            Dockerfiles, Compose, nginx
tests/fixtures/           Golden Metacritic HTML
.github/workflows/ci.yml  Lint, types, tests, schema drift, Compose config
llm-transcripts.jsonl     Agent chat log (raw JSONL)
```

Generated artifacts (`contracts/schemas/`, `contracts/asyncapi.yaml`, `apps/web/openapi.json`) are produced from Pydantic / FastAPI. Do not edit them by hand.
