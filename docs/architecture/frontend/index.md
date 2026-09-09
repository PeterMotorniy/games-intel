# Frontend Index

**Status**: Existing
**Last Updated**: 2026-09-09
**Stakeholders**: Frontend, Backend
**Related Docs**: [web-ui.md](web-ui.md), [../core/system-architecture.md](../core/system-architecture.md)

## Purpose

Индекс веб-интерфейса: каталог игр, карточка, фильтры, мониторинг пайплайна, ручной запуск.

## Key Principles

- Типы API сгенерированы из OpenAPI бэкенда, не дублируются руками.
- У каждого экрана есть loading / empty / error.
- Кнопка запуска публикует событие, а не вызывает воркеров напрямую.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| Web UI | Экраны, API, SSE, доступность | [web-ui.md](web-ui.md) |

## Diagrams / Visuals

См. [web-ui.md](web-ui.md).

## Trade-offs & Justifications

SPA (React) + FastAPI вместо серверного рендера: realtime SSE и отдельный контракт OpenAPI проще стыковать с демонами на Kafka.

## Technical Details

- **Technology Stack**: React, TypeScript, Vite, TanStack Query, EventSource.
- **Configuration & Env Vars**: [configuration.md](../core/configuration.md).
- **Dependencies & Versions**: Planned / 2026-09-07.
- **Testing Strategy**: контрактные тесты API, UI-состояния empty/error.
- **Deployment Considerations**: static build за reverse-proxy вместе с API.

## Quality Attributes

Accessibility, consistency состояния, perceived performance через SSE.
