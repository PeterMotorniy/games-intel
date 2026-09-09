# Monorepo and Tooling — Requirements

## Functional Requirements

- Новый разработчик по README устанавливает зависимости и гоняет проверки без ручного DDL.
- Каталоги соответствуют раскладке architecture; пустые пакеты импортируются.

## Technical Requirements

- Стек: Python 3.12, uv; pin в lock. [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md) § Technology Stack, § репозиторий.
- Качество: ruff format/lint, mypy strict, pytest. [AGENTS.md](../../../../../../AGENTS.md) § 2, 4 (Python).
- Секреты: example с пустыми значениями. [AGENTS.md](../../../../../../AGENTS.md) § 9; [configuration.md](../../../../../../docs/architecture/core/configuration.md) § Purpose.
- Front заглушка `apps/web` может появиться полноценно в Epic 4; каталог создать сейчас.

## Acceptance Criteria

- [x] `uv sync` успешен.
- [x] `ruff check`, `ruff format --check`, `mypy`, `pytest` зелёные на каркасе.
- [x] Нет langchain в зависимостях scheduler/discovery/catalog/similarity пакетов.
- [x] `.env.example` в git; реальные секреты нет.

## Constraints

- Не добавлять зависимости «на будущее», кроме явно нужных каркасу (pydantic-settings, pytest, ruff, mypy).
- Не коммитить venv, dist, media.
