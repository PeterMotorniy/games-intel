# Game Card — Requirements

## Functional Requirements

- Название, локальная обложка, платформы+Metascore+Userscore, разработчик, описание, ссылка на видео (скрыть если null).
- Жанр и дата выхода если заполнены.
- Блоки критиков и пользователей: likes/dislikes/summary или «собираем отзывы».
- Летсплей: ссылка + заключение или статусы no_video / transcript_unavailable / quota понятным текстом, не 500.
- Похожие: title, переход на /games/{slug}; self нет.
- Частичная гидратация нормальна.

## Technical Requirements

- [web-ui.md](../../../../../../docs/architecture/frontend/web-ui.md) § Карточка игры.
- [task.md](../../../../../../task.md) информация и similar.
- [similarity.md](../../../../../../docs/architecture/workers/similarity.md) hybrid score отображать не обязательно как сырой cosine.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) UI частичные блоки не 500.
- Cover URL /api/v1/media/covers/{slug}.

## Acceptance Criteria

- [x] Все обязательные поля рендерятся при полном фикстурном ответе.
- [x] Null video скрывает блок.
- [x] Клик similar меняет маршрут и данные.
- [x] Error/loading карточки.
- [x] Браузер: открыть карточку с списка, клик similar.

## Constraints

- Не показывать сырой транскрипт целиком.
- Исходные title/description не переводить принудительно.
