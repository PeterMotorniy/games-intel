# Core Architecture Index

**Status**: Existing
**Last Updated**: 2026-09-08
**Stakeholders**: AI Engineer, Backend, Frontend
**Related Docs**: [../index.md](../index.md)

## Purpose

Индекс обзора системы и конфигурации. Всё изменяемое — в configuration.md, не в коде.

## Key Principles

- Сначала обзор, затем configuration, затем воркеры и ошибки.
- Литералов топиков, cron и лимитов в обзоре нет — только ссылка на конфиг.

## Components & Interactions

| Domain | Description | Location |
|--------|-------------|----------|
| System Architecture | Текущий обзор пайплайна | [system-architecture.md](system-architecture.md) |
| Configuration | Полное дерево настроек | [configuration.md](configuration.md) |

## Diagrams / Visuals

См. связанные документы.

## Trade-offs & Justifications

Конфиг отдельным файлом: иначе обзор раздувается таблицами ключей.

## Technical Details

- **Technology Stack**: см. обзор.
- **Configuration & Env Vars**: [configuration.md](configuration.md).
- **Dependencies & Versions**: Existing / 2026-09-08.
- **Testing Strategy**: не применимо.
- **Deployment Considerations**: не применимо.

## Quality Attributes

Актуальность одного описания; изменяемость через конфиг.
