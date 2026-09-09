# Monorepo and Tooling — Index

## Overview

Создать каркас репозитория и пайплайн качества: uv workspace, пакеты-заглушки по раскладке architecture, ruff, mypy strict, pytest, `.env.example`. Родитель: [Phase_1_settings-and-contracts](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Единое место сборки всех сервисов тестового.
- **Business Impact**: Предсказуемый onboarding и CI.
- **User Value**: Косвенный.
- **Success Metrics**: `uv sync` + линт/типы/пустой pytest проходят.
- **Parent Alignment**: Старт фазы settings/contracts.

### Technical

- **Primary Technical Objective**: Каталоги `apps/`, `packages/`, `infra/compose/` как в system-architecture; Python 3.12; lock-файл.
- **Technical Impact**: Границы слоёв с первого коммита каркаса.
- **Implementation Scope**: Пустые пакеты/pyproject, без бизнес-логики.
- **Quality Standards**: [AGENTS.md](../../../../../../AGENTS.md) § 2, 9, 10.
- **Parent Alignment**: § «Репозиторная раскладка» [system-architecture.md](../../../../../../docs/architecture/core/system-architecture.md).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

Нет.

## Deliverables

- Дерево каталогов apps/api, apps/web (заглушка), apps/workers/*, apps/scrape/metacritic, packages/*, infra/compose.
- Корневой pyproject/uv workspace, ruff, mypy, pytest.ini.
- `.env.example`, `config.example.yaml` (минимальный, расширит Step 2).
- README с командами проверок (как только команды существуют — они должны работать).

## Notes

Образы Reviews/LetsPlay позже добавят langchain; сейчас langchain **не** в корневом обязательном dependency чистых демонов.
