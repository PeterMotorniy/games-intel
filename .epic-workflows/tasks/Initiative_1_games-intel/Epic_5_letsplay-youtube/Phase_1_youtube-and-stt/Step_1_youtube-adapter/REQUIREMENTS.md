# YouTube Adapter — Requirements

## Functional Requirements

1. Query из search_query_template (`{title} let's play`).
2. Отсев: duration вне [min_duration_seconds, max_duration_seconds]; title не содержит нормализованный тайтл; exclude_title_patterns (compilation, top 10, …).
3. Остаток sort view_count desc.
4. Воркер берёт items[0]; пустой список → no_video на уровне воркера.
- get_transcript: captions; unavailable валиден.
- get_audio: clip ≤ max_duration_seconds; только путь для STT.

## Technical Requirements

- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) YouTubePort отбор 1–4, get_transcript, get_audio.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) adapters.youtube.*.
- [worker-catalog.md](../../../../../../docs/architecture/workers/worker-catalog.md) LetsPlay шаг 1–4.
- Таймаут каждого вызова; ключ не в логах.

## Acceptance Criteria

- [x] Compilation отфильтрован даже с большим view_count.
- [x] Короткий ролик < min отсечён.
- [x] transcript_unavailable без исключения.
- [x] quota_exceeded код адаптера.

## Constraints

- Сортировка по просмотрам **после** релевантности.
- Адаптер не делает STT.
