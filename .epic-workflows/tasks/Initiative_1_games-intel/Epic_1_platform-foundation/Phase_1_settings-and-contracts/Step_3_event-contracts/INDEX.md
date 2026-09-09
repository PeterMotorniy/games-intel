# Event Contracts — Index

## Overview

Пакет `packages/contracts`: CloudEvents 1.0 конверт, все payload Pydantic-модели, JSON Schema, заготовка AsyncAPI, модели structured output агентов (`ReviewSummary`, LetsPlay conclusion). Родитель: [Phase_1_settings-and-contracts](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Воркеры и UI не изобретают «внутренний JSON».
- **Business Impact**: Совместимость реплик и эволюция аддитивная.
- **User Value**: Косвенный (стабильные поля карточки).
- **Success Metrics**: Golden JSON; битый конверт не проходит валидацию.
- **Parent Alignment**: Принцип единого контракта — system-architecture.

### Technical

- **Primary Technical Objective**: Модели из таблиц [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) § Payload-модели и § Конверт.
- **Technical Impact**: LLM structured output = подмножество тех же моделей.
- **Implementation Scope**: Нет consumer/producer runtime (Epic 1 Phase 3).
- **Quality Standards**: JSON Schema из моделей; `dataschema` указывает на актуальный JSON Schema контракта.
- **Parent Alignment**: event-contracts.md + configuration kafka.events.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 2 settings (имена type — defaults, код валидации type берёт settings позже; модели независимы).

## Deliverables

Pydantic-модели всех `data`; CloudEvent envelope; генератор schema; golden fixtures; модели PlatformScore, ReviewSnippet (для адаптеров — можно здесь или в adapters DTO, канон event-contracts + adapters: ReviewSnippet в Port).

## Notes

Числа скоров: metascore `int | null`, userscore `float | null`. Datetime timezone-aware UTC.
