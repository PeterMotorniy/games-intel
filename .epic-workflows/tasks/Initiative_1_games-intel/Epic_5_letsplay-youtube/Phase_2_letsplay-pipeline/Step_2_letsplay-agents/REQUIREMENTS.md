# LetsPlay Agents — Requirements

## Functional Requirements

- TranscriptionAgent: ainvoke({ audio_ref }) → { text, language }; не YouTube.
- LetsPlayAnalystAgent: ainvoke({ video_title, transcript_excerpt }) → { conclusion, highlights[] } русский.
- STT выключен — воркер не вызывает Transcription.
- Schema retry как у ReviewSummarizer.

## Technical Requirements

- [agent-catalog.md](../../../../../../docs/architecture/agents/agent-catalog.md) оба компонента.
- [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) LLM subset conclusion/highlights.
- [configuration.md](../../../../../../docs/architecture/core/configuration.md) prompts.letsplay_analyst_path, llm.*, stt.enabled.
- [error-handling.md](../../../../../../docs/architecture/reliability/error-handling.md) агенты.
- [recovery.md](../../../../../../docs/architecture/reliability/recovery.md) thread_id `{run_id}:{slug}:{agent_name}`.
- Промпт файл с контрактом; недоверенный транскрипт как data.
- Testing fake LLM/STT; без Kafka.

## Acceptance Criteria

- [x] Structured conclusion без regex.
- [x] Transcription только SttPort.
- [x] LangSmith optional degrade.
- [x] letsplay image имеет langchain; similarity нет.

## Constraints

- Три маленьких агента лучше одного graph на всю игру — не объединять с ReviewSummarizer.
- Не отправлять полный час транскрипта — excerpt после max_chars.
