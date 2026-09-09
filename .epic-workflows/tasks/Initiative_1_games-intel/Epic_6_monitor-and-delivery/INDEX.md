# Monitor and Delivery — Index

## Overview

Дополнительная часть 2 ТЗ: realtime-монитор реплик и пайплайна, circuit sidecar, кнопка запуска. Плюс recovery-тесты, полная Compose-сборка с репликами, выравнивание docs и артефакты сдачи. Пункт 6 Implementation Plan.

## Goals

### Business

- **Primary Business Objective**: Оператор видит, жив ли пайплайн, и может запустить обработку; стенд готов к сдаче.
- **Business Impact**: Закрывает доп. 2 и блок «Результат тестового» в [task.md](../../../../task.md).
- **User Value**: Прозрачность воркеров, failed/degraded, курсор суток, parse_error.
- **Success Metrics**: SSE кадры; POST `/runs` → 202; две строки Catalog при двух репликах; ссылка на сервис.
- **Parent Alignment**: Доп. 2 + сдача инициативы.

### Technical

- **Primary Technical Objective**: Heartbeats, GET `/monitor` + SSE, POST tick через outbox, матрица ошибок, kill-тесты, Compose replicas, health.
- **Technical Impact**: Operability без оркестратора; UI не ходит в Kafka.
- **Implementation Scope**: Replay одной стадии — CLI вне MVP UI ([recovery.md](../../../../docs/architecture/reliability/recovery.md) § 7).
- **Quality Standards**: Не светить секреты; не кэшировать `/monitor`; алерты P0 не на каждый degraded.
- **Parent Alignment**: [web-ui.md](../../../../docs/architecture/frontend/web-ui.md) монитор, [error-handling.md](../../../../docs/architecture/reliability/error-handling.md), [recovery.md](../../../../docs/architecture/reliability/recovery.md), [replicas-and-idempotency.md](../../../../docs/architecture/workers/replicas-and-idempotency.md).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1–5: воркеры пишут items/heartbeats; API каталога есть; sidecar пишет `adapter_health`.

## Deliverables

- Экран монитора + SSE + кнопка «Запустить сейчас».
- Тесты error matrix и recovery (attempt_count, outbox unpublished, checkpoint агента).
- Полный Compose: контейнер на воркер, replicas, sidecar, api, web, postgres, kafka, volume обложек, один cron при `tick_source=external`.
- Docs status Existing где реализовано; README запуска.

## Child tasks

| # | Phase |
|---|-------|
| 1 | [Phase_1_realtime-monitor](Phase_1_realtime-monitor/INDEX.md) |
| 2 | [Phase_2_reliability-and-delivery](Phase_2_reliability-and-delivery/INDEX.md) |

## Notes

Кнопка создаёт новый tick (`trigger=manual`), не retry slug X.
