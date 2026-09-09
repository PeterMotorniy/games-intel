# Kafka and Outbox — Index

## Overview

Клиент Kafka (producer/consumer CloudEvents JSON), создание сообщений с детерминированным idempotencykey, outbox relay в процессе воркера. Родитель: [Phase_3_daemon-runtime](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Домен сохраняется даже если брокер недоступен (unpublished outbox).
- **Success Metrics**: После рестарта unpublished строки публикуются.
- **Parent Alignment**: Транзакционный outbox data-model.

### Technical

- **Primary Technical Objective**: `packages/kafka` + OutboxRepository claim/publish/mark.
- **Implementation Scope**: Нет полного daemon loop (следующий шаг).
- **Quality Standards**: Ключ партиции slug/run_id; headers/value CloudEvents.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Settings, contracts, OutboxRepository.

## Deliverables

Сериализация CloudEvent; producer; consumer poll; relay loop `producer=worker_type`; тесты на fake broker или testcontainers.
