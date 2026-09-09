# STT Port — Requirements

## Functional Requirements

- ainvoke/transcribe(audio_ref) → { text, language }.
- provider: faster_whisper | deepgram | assemblyai.
- enabled зеркало letsplay.stt_enabled default false.
- Долгое аудио отсекается **до** вызова (воркер/youtube max duration).
- Fail → retry затем degrade на уровне воркера.

## Technical Requirements

- [agent-catalog.md](../../../../../../docs/architecture/agents/agent-catalog.md) таблица провайдеров.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) stt.* (model_size, device, cloud keys/models, timeout 120).
- [adapters.md](../../../../../../docs/architecture/integrations/adapters.md) STT runtime.
- Нет ключа cloud при cloud provider: ошибка старта процесса STT/LetsPlay либо degrade если enabled=false.
- LangSmith span опционален вокруг вызова — в агенте, не обязательно в Port.

## Acceptance Criteria

- [x] Fake provider возвращает текст.
- [x] enabled=false: воркер не создаёт Port вызов (тест воркера позже).
- [x] Timeout соблюдён.
- [x] Секреты не в логах.

## Constraints

- TranscriptionAgent не ходит на YouTube.
- Нет отдельного STT Kafka worker.
