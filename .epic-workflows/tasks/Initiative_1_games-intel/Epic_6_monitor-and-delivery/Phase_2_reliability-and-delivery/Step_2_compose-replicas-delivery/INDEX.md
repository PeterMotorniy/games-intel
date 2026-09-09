# Compose Replicas Delivery — Index

## Overview

Полный Docker Compose контур, реплики, cron tick, volumes, README, выравнивание architecture docs под реализованное. Родитель: [Phase_2_reliability-and-delivery](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Сдаваемый стенд: открыл UI — виден каталог и монитор.
- **Success Metrics**: Одна команда up; health green; реплики в мониторе.
- **Parent Alignment**: task.md ссылка на сервис + репозиторий.

### Technical

- **Primary Technical Objective**: infra/compose полный; partitions ≥ replicas; instance_id HOSTNAME; langchain только reviews/letsplay images.
- **Implementation Scope**: Публичный URL — вне репо (инструкция). JSONL переписки не обязателен в git.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Все сервисы собраны; тесты шага 1.

## Deliverables

compose.yml services; cron container; README; docs status Existing; проверка lint/types/tests.
