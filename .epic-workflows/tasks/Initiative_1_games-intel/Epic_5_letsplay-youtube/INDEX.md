# LetsPlay YouTube — Index

## Overview

Дополнительная часть 1 ТЗ: поиск релевантного популярного летсплея, текст рассказа (субтитры или STT), заключение на русском, ссылка на ролик. Пункт 5 Implementation Plan.

## Goals

### Business

- **Primary Business Objective**: В карточке — блок летсплея с роликом и выводами блогера.
- **Business Impact**: Плюс при оценке тестового; честные статусы при отсутствии данных.
- **User Value**: Быстро понять впечатление с летсплея, не смотря час видео.
- **Success Metrics**: Берётся `items[0]` после фильтра релевантности и сортировки по просмотрам; нет ролика ≠ ошибка страницы.
- **Parent Alignment**: Доп. часть 1 [task.md](../../../../task.md).

### Technical

- **Primary Technical Objective**: YouTubePort + SttPort + LetsPlayWorker + TranscriptionAgent + LetsPlayAnalystAgent.
- **Technical Impact**: STT по умолчанию выключен; облачные ключи только env.
- **Implementation Scope**: Нет отдельного Kafka-демона STT. Поиск/captions/audio — адаптер, не агент.
- **Quality Standards**: Таймауты; обрезка транскрипта до вызова LLM; тесты без сети.
- **Parent Alignment**: [adapters.md](../../../../docs/architecture/integrations/adapters.md), [agent-catalog.md](../../../../docs/architecture/agents/agent-catalog.md), worker LetsPlay.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- Epic 1: contracts `GameLetsPlayAnalyzed`, daemon, exceptions QuotaError.
- Epic 2: `game.discovered`.
- Epic 4 UI: отображение блока (карточка уже умеет частичные данные).

## Deliverables

- YouTube adapter: search, transcript, optional get_audio.
- SttPort: faster-whisper default, deepgram/assemblyai overlay.
- LetsPlayWorker поток 1–6 из каталога воркеров.
- Два агента: STT wrap + analyst structured conclusion/highlights.

## Child tasks

| # | Phase |
|---|-------|
| 1 | [Phase_1_youtube-and-stt](Phase_1_youtube-and-stt/INDEX.md) |
| 2 | [Phase_2_letsplay-pipeline](Phase_2_letsplay-pipeline/INDEX.md) |

## Notes

Скачивание медиа — YouTubePort. TranscriptionAgent только `audio_ref` → text.
