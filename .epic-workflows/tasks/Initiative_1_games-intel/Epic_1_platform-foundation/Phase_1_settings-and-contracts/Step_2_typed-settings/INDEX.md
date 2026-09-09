# Typed Settings — Index

## Overview

Реализовать `packages/settings`: одно дерево Pydantic Settings v2, yaml + overlay `GAMES_INTEL__*`, strict неизвестные ключи, defaults из канона configuration.md. Родитель: [Phase_1_settings-and-contracts](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Смена часа запуска, имени топика и group id — операция конфига.
- **Business Impact**: Стенды local/staging/prod без форка кода.
- **User Value**: Косвенный.
- **Success Metrics**: Тест «topic из settings»; запрет разных group у реплик задокументирован/проверен на уровне модели (один ключ group на тип).
- **Parent Alignment**: «Всё изменяемое в settings» — [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md) принцип 7.

### Technical

- **Primary Technical Objective**: Полное дерево ключей [configuration.md](../../../../../../docs/architecture/core/configuration.md).
- **Technical Impact**: `os.environ` вне settings запрещён (линтер/конвенция + отсутствие чтений в пакетах).
- **Implementation Scope**: Только пакет settings + example yaml.
- **Quality Standards**: Strict; секреты нелогируемые.
- **Parent Alignment**: configuration.md целиком.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Step 1 монорепо.

## Deliverables

Класс(ы) settings, загрузчик yaml+env, `config.example.yaml` со всеми секциями и пустыми секретами, unit-тесты parse/overlay/unknown key.

## Notes

`client_id` шаблон `{app.name}-{worker.type}-{instance_id}`. `instance_id` из env HOSTNAME/uuid — overlay.
