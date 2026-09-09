# Error and Recovery Tests — Index

## Overview

Систематические тесты политики ошибок и рестарта процесса на fake Port/LLM. Родитель: [Phase_2_reliability-and-delivery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Уверенность, что час listing fail не отравляет БД, а kill не плодит дубли.
- **Success Metrics**: Матрица error-handling + recovery зелёная.
- **Parent Alignment**: Надёжность сдачи.

### Technical

- **Primary Technical Objective**: pytest матрица без сети.
- **Implementation Scope**: Не live Metacritic.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Все воркеры и daemon loop.

## Deliverables

Тесты listed in architecture Testing Strategy sections.
