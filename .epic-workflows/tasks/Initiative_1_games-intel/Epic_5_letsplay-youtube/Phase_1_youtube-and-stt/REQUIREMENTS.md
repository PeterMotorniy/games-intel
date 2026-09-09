# YouTube and STT Phase — Requirements

## Functional Requirements

- search_letsplays: query template, duration filter, title relevance, exclude patterns, sort view_count desc.
- get_transcript: ok | transcript_unavailable, max_chars truncated.
- get_audio только если STT включён; max_duration; не выполняет STT.
- SttPort: audio_ref → text, language; timeout; provider из конфига.

## Technical Requirements

- [adapters.md](../../../../../docs/architecture/integrations/adapters.md) YouTubePort, STT runtime.
- [configuration.md](../../../../../docs/architecture/core/configuration.md) adapters.youtube.*, stt.*, letsplay.max_video_duration_seconds.
- [agent-catalog.md](../../../../../docs/architecture/agents/agent-catalog.md): поиск не агент; STT вызывается из TranscriptionAgent.
- QuotaError mapping.
- YouTube Data API v3; captions; ключ только env.

## Acceptance Criteria

- [x] Фильтры на фикстурных VideoHit без API.
- [x] Пустой items валиден.
- [x] stt enabled=false: get_audio не обязателен к реализации вызова из воркера.
- [x] Нет ключа deepgram при provider=deepgram и enabled → fail start или degrade per docs.

## Constraints

- Без браузера на YouTube.
- Агенты не вызывают YouTubePort.
