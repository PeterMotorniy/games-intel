# Integrations Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend
**Related Docs**: [adapters.md](adapters.md), [scraping-resilience.md](scraping-resilience.md), [../workers/worker-catalog.md](../workers/worker-catalog.md)

## Purpose

Индекс внешних интеграций. HTTP, селекторы, SDK YouTube, STT-провайдеры и файлы обложек живут только за типизированными Port в `packages/adapters`.

## Key Principles

- Воркеры не конструируют запросы к Metacritic и YouTube.
- Агенты порты не вызывают: им данные отдаёт демон.
- Недоверенный внешний контент передаётся в LLM как данные, не как инструкции.
- Таймауты, rate limit, circuit breaker — ответственность адаптера/sidecar.
- Скрейпинг — first-class риск, не деталь клиента.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Adapters | Ports Metacritic/YouTube/media/STT, scrape sidecar | [adapters.md](adapters.md) |
| Scraping Resilience | Fail-closed, кеш, circuit, canary, обложки | [scraping-resilience.md](scraping-resilience.md) |

## Diagrams / Visuals

См. связанные документы.

## Trade-offs & Justifications

HTTP sidecar для Playwright даёт единый rate limit и пул браузера на все реплики воркеров. Kafka — шина между демонами, не транспорт к сайтам.

## Technical Details

- **Technology Stack**: httpx, Playwright sidecar, YouTube Data API, captions, OpenAI Whisper API.
- **Configuration & Env Vars**: [configuration.md](../core/configuration.md) — `adapters.*`, `media.*`, `stt.*`.
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: контрактные тесты портов на фикстурах HTML/JSON, без сети в unit.
- **Deployment Considerations**: scrape sidecar только в docker network; volume обложек.

## Quality Attributes

Изоляция внешней хрупкости, security границ, maintainability селекторов, operability parse_error.
