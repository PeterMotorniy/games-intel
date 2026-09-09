# Web Catalog Phase — Requirements

## Functional Requirements

- Список: обложка, title, developer, агрегированный Metascore, платформы-чипы; поиск, select платформы, сортировка; клик → /games/{slug}.
- Empty: «Игр пока нет».
- Карточка: поля ТЗ; скрыть видео если null; резюме или «собираем отзывы»; letsplay статусы текстом если колонки пусты/заполнены; similar клик.
- UI на русском; title/description как с Metacritic.
- Loading/error на каждом экране.

## Technical Requirements

- [web-ui.md](../../../../../docs/architecture/frontend/web-ui.md) экраны, клиентская раскладка, a11y.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) web.api_base_url.
- [AGENTS.md](../../../../../AGENTS.md) § 4 Frontend.
- Типы только OpenAPI codegen.
- prefers-reduced-motion; alt=title; клавиатура.

## Acceptance Criteria

- [x] Фильтры в Query keys.
- [x] Компонентные тесты empty/error.
- [x] Браузерная проверка списка и карточки (Playwright MCP или против stub).
- [x] Фокус-видимость, кнопки-кнопки.

## Constraints

- Не ручной fetch в useEffect без api layer.
- Не дублировать DTO.
