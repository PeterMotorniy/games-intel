# LetsPlay YouTube — Requirements

## Functional Requirements

- По `game.discovered` найти летсплеи, отфильтровать, отсортировать по `view_count`, взять первый.
- Нет роликов → `status=no_video`, агенты не вызываются.
- Субтитры ok → текст готов. Иначе если STT включён — audio + TranscriptionAgent; иначе `transcript_unavailable`.
- Quota YouTube → `quota_exceeded`, degrade, без retry до окна.
- При тексте — LetsPlayAnalystAgent: `conclusion`, `highlights` на русском; persist + `game.letsplay.analyzed`.
- Карточка UI уже из Epic 4 показывает статусы понятным текстом ([web-ui.md](../../../../docs/architecture/frontend/web-ui.md)).

## Technical Requirements

- YouTubePort: `search_letsplays`, `get_transcript`, `get_audio` — [adapters.md](../../../../docs/architecture/integrations/adapters.md).
- Отбор: query template `{title} let's play`; duration `[min,max]`; title содержит нормализованный тайтл; exclude compilation/top 10; сортировка просмотров **после** фильтра.
- Конфиг `adapters.youtube.*`, `letsplay.*`, `stt.*` — [configuration.md](../../../../docs/architecture/core/configuration.md).
- LetsPlayWorker поток: [worker-catalog.md](../../../../docs/architecture/workers/worker-catalog.md).
- Агенты: [agent-catalog.md](../../../../docs/architecture/agents/agent-catalog.md). Analyst режет текст **воркер** до `transcript_max_chars`.
- SttPort провайдеры: faster_whisper / deepgram / assemblyai. Нет ключа cloud при выбранном cloud-провайдере — ошибка старта или degrade если `enabled=false`.
- Ошибки: [error-handling.md](../../../../docs/architecture/reliability/error-handling.md) — quota degrade; STT fail retry затем degrade; LLM fail после лимита — stage failed.
- Контракт: [event-contracts.md](../../../../docs/architecture/events/event-contracts.md) `GameLetsPlayAnalyzed`. Check constraint статуса — [data-model.md](../../../../docs/architecture/database/data-model.md).
- Промпт: `prompts.letsplay_analyst_path`.

## Acceptance Criteria

- [x] Compilation/top-10 отсекаются; короткий тизер вне min_duration не берётся.
- [x] Пустой поиск: `no_video`, 0 вызовов агентов.
- [x] transcript_unavailable + stt_enabled=false: без audio download.
- [x] Fake STT fail → degrade, карточка живая.
- [x] Structured conclusion без regex.
- [x] LetsPlay колонки не затирают reviews/catalog.
- [x] Идемпотентность стадии `letsplay`.

## Constraints

- Агенты не ходят в YouTube Data API.
- Ключ API только в youtube-адаптере / env overlay.
- STT default false для лёгкого демо.
- Сырой транскрипт целиком не в логи и не в монитор.
