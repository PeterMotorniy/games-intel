# Event Contracts — Requirements

## Functional Requirements

- Валидация конверта отклоняет сообщение без `idempotencykey` или с неверным `specversion`.
- Payload соответствует таблице топиков: ScheduleTick, RunRequested, GameDiscovered, GameCataloged, GameReviewsSummarized, GameLetsPlayAnalyzed, GameSimilarAssigned, SimilarityRecomputeRequested, WorkerHeartbeat, DeadLetter.
- `SimilarGameRef.score` — float hybrid; `GameLetsPlayAnalyzed.status` — enum `ok | no_video | transcript_unavailable | quota_exceeded`.
- LLM использует ReviewSummary и `{conclusion, highlights}` без свободного текста.

## Technical Requirements

- Канон: [event-contracts.md](../../../../../../docs/architecture/events/event-contracts.md) полностью (конверт, каталог топиков, payload, валидация, AsyncAPI).
- Имена type — defaults из [configuration.md](../../../../../../docs/architecture/core/configuration.md) `kafka.events.*`; в моделях нет «вечных» констант топиков как единственного источника (type при сборке события читает settings — хелпер можно здесь).
- Ключ Kafka = subject (slug) или run_id — правило в документации контракта; сериализация ключа в Phase 3.
- Эволюция только аддитивная; версия в `dataschema`.
- AdapterError DTO можно держать в contracts или adapters; код ошибок как в [adapters.md](../../../../../../docs/architecture/integrations/adapters.md).

## Acceptance Criteria

- [x] Golden JSON на каждый payload type.
- [x] Обязательный idempotencykey.
- [x] Два события с разным `id` и одним business key валидны как конверты (дедуп — БД, Phase 3).
- [x] CI генерирует JSON Schema и фрагмент AsyncAPI 3 (`servers.kafka`, channels, operations без «кого вызывать»).
- [x] Metascore tbd → null, не 0.

## Constraints

- Не писать JSON Schema руками параллельно моделям.
- Не разбирать LLM-текст regex (запрет на уровне моделей structured output).
