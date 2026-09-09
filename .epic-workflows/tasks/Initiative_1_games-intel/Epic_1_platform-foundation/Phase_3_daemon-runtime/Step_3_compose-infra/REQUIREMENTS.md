# Compose Infra — Requirements

## Functional Requirements

- Postgres 16, расширения vector и pg_trgm доступны (миграции применяет приложение/job).
- Kafka KRaft, топики для всех `kafka.events.*` с partitions.game_events / partitions.control.
- Health/ready postgres и kafka.

## Technical Requirements

- [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md) § Deployment: postgres, kafka.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) partitions, replication_factor, retention_hours.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) § Deployment: init-контейнер создаёт топики из конфига.
- `database.url` из env overlay в example compose.

## Acceptance Criteria

- [x] compose up infra без ручного создания топиков.
- [x] Число партиций game-топиков ≥ 6 default (или из yaml).
- [x] Данные postgres на volume.
- [x] Документированная команда в README.

## Constraints

- Не публиковать Kafka на мир в prod-профиле без нужды; для демо localhost ок.
- Не класть пароли в git кроме пустого example.
