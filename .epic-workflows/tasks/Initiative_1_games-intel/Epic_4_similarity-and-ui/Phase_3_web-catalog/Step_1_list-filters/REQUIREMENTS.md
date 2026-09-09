# List Filters — Requirements

## Functional Requirements

- Краткая карточка: обложка, title, developer, агрегированный Metascore, чипы платформ.
- Контролы: поиск по названию, select платформы, сортировка metascore|userscore|title|updated.
- Клик по строке → /games/{slug}.
- Empty: «Игр пока нет» (+ ссылка на монитор можно отложить до Epic 6).
- Loading и error.

## Technical Requirements

- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) § Список игр, a11y, Query keys.
- [task.md](../../../../../../task.md) список, фильтр, поиск, сортировка.
- [AGENTS.md](../../../../../../AGENTS.md) frontend states.
- prefers-reduced-motion без бесконечного shimmer.
- Cover img alt=title.

## Acceptance Criteria

- [x] Смена фильтра перезапрашивает API (Query).
- [x] Клавиатурой доступны search/select/sort/карточки.
- [x] Empty и error покрыты.
- [x] Проверка в браузере: поиск и фильтр меняют список.

## Constraints

- Типы из OpenAPI.
- Не ходить в Kafka с клиента.
