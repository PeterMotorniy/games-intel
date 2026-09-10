from __future__ import annotations

import os
import uuid
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

_STRICT = ConfigDict(extra="forbid")


def _api_origin(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed.netloc.lower()


def default_instance_id() -> str:
    hostname = os.environ.get("HOSTNAME", "").strip()
    if hostname:
        return hostname
    return str(uuid.uuid4())


class AppSettings(BaseModel):
    model_config = _STRICT

    name: str = "games-intel"
    env: Literal["local", "staging", "prod"] = "local"
    log_level: str = "INFO"
    process_timezone: str = "UTC"
    http_timeout_seconds: int = 30


class KafkaPartitionsSettings(BaseModel):
    model_config = _STRICT

    game_events: int = 6
    control: int = 3


class KafkaEventsSettings(BaseModel):
    model_config = _STRICT

    schedule_tick: str = "ingestion.schedule.tick"
    run_requested: str = "ingestion.run.requested"
    page_listed: str = "games.page.listed"
    game_listed: str = "game.listed"
    game_cataloged: str = "game.cataloged"
    game_reviews_summarized: str = "game.reviews.summarized"
    game_letsplay_analyzed: str = "game.letsplay.analyzed"
    game_similar_assigned: str = "game.similar.assigned"
    similarity_recompute: str = "similarity.recompute.requested"
    worker_heartbeat: str = "worker.heartbeat"
    dlq: str = "ingestion.dlq"

    def resolve(self, key: str) -> str:
        try:
            return str(getattr(self, key))
        except AttributeError as exc:
            msg = f"unknown kafka.events key: {key}"
            raise KeyError(msg) from exc


class KafkaConsumerGroupsSettings(BaseModel):
    model_config = _STRICT

    scheduler: str = "games-intel.scheduler"
    discovery: str = "games-intel.discovery"
    catalog: str = "games-intel.catalog"
    reviews: str = "games-intel.reviews"
    letsplay: str = "games-intel.letsplay"
    similarity: str = "games-intel.similarity"

    def resolve(self, key: str) -> str:
        try:
            return str(getattr(self, key))
        except AttributeError as exc:
            msg = f"unknown kafka.consumer_groups key: {key}"
            raise KeyError(msg) from exc


class KafkaSettings(BaseModel):
    model_config = _STRICT

    bootstrap_servers: str = "localhost:9092"
    client_id: str = "{app.name}-{worker.type}-{instance_id}"
    security_protocol: str = ""
    sasl_mechanism: str = ""
    sasl_username: str = ""
    sasl_password: SecretStr = SecretStr("")
    partitions: KafkaPartitionsSettings = Field(default_factory=KafkaPartitionsSettings)
    replication_factor: int = 1
    retention_hours: int = 168
    enable_auto_commit: bool = False
    max_poll_records: int = 10
    max_poll_interval_ms: int = 600_000
    session_timeout_ms: int = 45_000
    events: KafkaEventsSettings = Field(default_factory=KafkaEventsSettings)
    consumer_groups: KafkaConsumerGroupsSettings = Field(
        default_factory=KafkaConsumerGroupsSettings
    )
    topic_prefix: str = ""


class IdempotencySettings(BaseModel):
    model_config = _STRICT

    key_template: str = "{event_type}:{run_id}:{subject}:{stage}"
    enable_event_id_unique: bool = True
    enable_business_key_unique: bool = True


class _InstanceIdMixin(BaseModel):
    instance_id: str = Field(default_factory=default_instance_id)

    @model_validator(mode="after")
    def fill_blank_instance_id(self) -> _InstanceIdMixin:
        if not self.instance_id.strip():
            self.instance_id = default_instance_id()
        return self


class SchedulerSettings(_InstanceIdMixin):
    model_config = _STRICT

    tick_source: Literal["external", "in_process"] = "external"
    tick_cron: str = "0 * * * *"
    tick_interval_seconds: int = 3600
    tick_use_interval: bool = False
    advisory_lock_key: int = 742001
    tick_dedup_window_seconds: int = 300
    default_limit: int = 20
    new_releases_source: str = "new_releases"
    browse_source: str = "browse"
    enabled: bool = True
    consumer_group: str = "scheduler"
    subscribe_event: str = "schedule_tick"
    publish_event: str = "run_requested"
    stage_name: str = "scheduled"
    heartbeat_interval_seconds: int = 10
    lease_seconds: int = 120


class WorkerSliceSettings(_InstanceIdMixin):
    model_config = _STRICT

    enabled: bool = True
    consumer_group: str
    subscribe_event: str
    publish_event: str
    stage_name: str
    heartbeat_interval_seconds: int = 10
    lease_seconds: int = 120


class DiscoverySettings(WorkerSliceSettings):
    consumer_group: str = "discovery"
    subscribe_event: str = "run_requested"
    publish_event: str = "game_listed"
    stage_name: str = "discovered"
    list_limit: int = 20
    browse_list_limit: int = 48


class CatalogSettings(WorkerSliceSettings):
    consumer_group: str = "catalog"
    subscribe_event: str = "game_listed"
    publish_event: str = "game_cataloged"
    stage_name: str = "cataloged"
    empty_video_ok: bool = True


class ReviewsSettings(WorkerSliceSettings):
    consumer_group: str = "reviews"
    subscribe_event: str = "game_cataloged"
    publish_event: str = "game_reviews_summarized"
    stage_name: str = "reviews"
    critic_limit: int = 50
    user_limit: int = 50
    max_chars: int = 8000
    skip_agent_if_empty: bool = True


class LetsPlaySettings(WorkerSliceSettings):
    consumer_group: str = "letsplay"
    subscribe_event: str = "game_cataloged"
    publish_event: str = "game_letsplay_analyzed"
    stage_name: str = "letsplay"
    search_max_results: int = 10
    stt_enabled: bool = True
    transcript_max_chars: int = 4_000
    # STT clip length (seconds from the start of the video). Search length
    # filters live on adapters.youtube.min_duration_seconds / max_duration_seconds.
    max_video_duration_seconds: int = 180


class SimilaritySettings(WorkerSliceSettings):
    consumer_group: str = "similarity"
    subscribe_event: str = "game_cataloged"
    subscribe_reviews_event: str = "game_reviews_summarized"
    subscribe_recompute_event: str = "similarity_recompute"
    publish_event: str = "game_similar_assigned"
    stage_name: str = "similar"
    k: int = 5
    mode: Literal["inline_all", "incremental"] = "incremental"
    inline_all_max_rows: int = 2000
    recompute_on_reviews: bool = True
    w_vector: float = 0.70
    w_platform: float = 0.15
    w_genre: float = 0.10
    w_release: float = 0.05
    release_tau_days: int = 365
    full_recompute_cron: str = "15 * * * *"
    reverse_candidate_limit: int = 50
    hnsw_min_rows: int = 5000
    emit_assigned_for_all: bool = False


class RetrySettings(BaseModel):
    model_config = _STRICT

    max_attempts: int = 5
    backoff_base_seconds: float = 1
    backoff_max_seconds: float = 60
    jitter_ratio: float = 0.2
    llm_structure_retries: int = 2
    prepare_timeout_seconds: float = 90


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    url: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("url", "DATABASE_URL"),
    )
    pool_size: int = 5
    pool_timeout_seconds: int = 30
    auto_migrate: bool = False


class MetacriticMarkersSettings(BaseModel):
    model_config = _STRICT

    listing_container: str = (
        '[data-testid="new-game-release-carousel"], .c-pageProductHome'
    )
    browse_listing_container: str = (
        '[data-testid="filter-results"], .c-finderSitePage'
    )
    listing_min_cards: int = 1
    listing_section_title: str = (
        ".c-sectionHeader_title, [data-testid='new-game-release-carousel'] h2, h1"
    )
    card_container: str = '[data-testid="product-hero"], .product-hero, .c-productHero'
    reviews_container: str = (
        '[data-testid="reviews-filters"], [data-testid="score-card-overview"], '
        '[data-testid="review-card"], [data-testid="product-reviews"], '
        '[data-testid="critic-reviews"], [data-testid="user-reviews"], '
        ".c-pageProductReviews, [data-gi-reviews]"
    )


class MetacriticListingSelectors(BaseModel):
    model_config = _STRICT

    game_card: str = '[data-testid="product-card"], .c-productCard, .c-finderProductCard'
    slug: str = "a[href*='/game/']"
    title: str = (
        "[data-testid='product-card-title'], [data-testid='product-title'], "
        "[data-testid='article-card-title'], .c-productCard_title, "
        ".c-finderProductCard_title, h3"
    )


class MetacriticCardSelectors(BaseModel):
    model_config = _STRICT

    title: str = (
        '[data-testid="hero-title"], h1.hero-title__text, h1.c-productHero_title, '
        ".c-productHero_title h1, h1"
    )
    cover: str = 'img.c-productHero_image, .c-productHero img, [data-testid="product-hero"] img'
    developer: str = (
        ".c-gameDetails_Developer .c-gameDetails_listItem, [data-testid='hero-summary-developer']"
    )
    publisher: str = (
        ".c-gameDetails_Distributor .c-gameDetails_listItem, [data-testid='hero-summary-publisher']"
    )
    description: str = (
        '.c-productHero_summary, .c-pageProduct_description, [data-testid="hero-summary"]'
    )
    video: str = (
        "iframe[src*='youtube'], a[href*='youtube.com'], a[href*='youtu.be'], "
        '[data-testid="featured-trailer"]'
    )
    platforms: str = '.c-gamePlatforms_item, [data-testid="product-score-card"]'
    platform_code: str = ".c-gamePlatforms_name, [data-platform], [title]"
    metascore: str = ".c-siteReviewScore, [data-gi-metascore]"
    userscore: str = ".c-siteReviewScore_user, [data-gi-userscore]"
    genres: str = ".c-gameDetails_Genre .c-gameDetails_listItem, .c-genreList_item"
    release_date: str = ".c-gameDetails_ReleaseDate .c-gameDetails_listItem"


class MetacriticReviewsSelectors(BaseModel):
    model_config = _STRICT

    critic_item: str = ".c-siteReview_critic, [data-gi-critic-review], [data-testid='review-card']"
    user_item: str = ".c-siteReview_user, [data-gi-user-review], [data-testid='review-card']"
    body: str = ".c-siteReview_quote, [data-gi-review-body], [data-testid='review-quote-text']"
    score: str = ".c-siteReviewScore, [data-gi-review-score]"
    author: str = (
        ".c-siteReview_author, [data-gi-review-author], [data-testid='review-card-header']"
    )


class MetacriticSelectorsSettings(BaseModel):
    model_config = _STRICT

    listing: MetacriticListingSelectors = Field(default_factory=MetacriticListingSelectors)
    card: MetacriticCardSelectors = Field(default_factory=MetacriticCardSelectors)
    reviews: MetacriticReviewsSelectors = Field(default_factory=MetacriticReviewsSelectors)


class MetacriticAdapterSettings(BaseModel):
    model_config = _STRICT

    base_url: str = "https://www.metacritic.com"
    sidecar_base_url: str = "http://scrape-metacritic:8080"
    sidecar_token: SecretStr = SecretStr("")
    mode: Literal["sidecar", "in_process"] = "sidecar"
    timeout_seconds: int = 30
    min_delay_ms: int = 1500
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    locale: str = "en-US"
    headless: bool = True
    pool_size: int = 1
    new_releases_path: str = "/game/"
    browse_path: str = "/browse/game/all/all/all-time/new/"
    browse_page_query_param: str = "page"
    cache_ttl_seconds: int = 3600
    canary_enabled: bool = True
    canary_slug: str = "elden-ring"
    circuit_fail_threshold: int = 3
    circuit_open_seconds: int = 600
    markers: MetacriticMarkersSettings = Field(default_factory=MetacriticMarkersSettings)
    selectors: MetacriticSelectorsSettings = Field(default_factory=MetacriticSelectorsSettings)


class YoutubeAdapterSettings(BaseModel):
    model_config = _STRICT

    # Unused: search/captions/audio go through yt-dlp. Kept so env overlay still loads.
    api_key: SecretStr = SecretStr("")
    timeout_seconds: int = 30
    search_query_template: str = "{title} let's play"
    # Fallback clip length for downloads. Worker override: letsplay.max_video_duration_seconds.
    clip_seconds: int = 180
    min_duration_seconds: int = 180
    max_duration_seconds: int = 7200
    exclude_title_patterns: list[str] = Field(default_factory=lambda: ["compilation", "top 10"])


class AdaptersSettings(BaseModel):
    model_config = _STRICT

    metacritic: MetacriticAdapterSettings = Field(default_factory=MetacriticAdapterSettings)
    youtube: YoutubeAdapterSettings = Field(default_factory=YoutubeAdapterSettings)


class MediaSettings(BaseModel):
    model_config = _STRICT

    covers_dir: str = "/data/covers"
    covers_url_prefix: str = "/api/v1/media/covers"
    covers_cache_control: str = "public, max-age=86400"


class SttSettings(BaseModel):
    model_config = _STRICT

    enabled: bool = True
    timeout_seconds: int = 120
    model: str = "whisper-1"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr = SecretStr("")
    max_audio_bytes: int = 25_000_000


class LlmSettings(BaseModel):
    model_config = _STRICT

    model: str = "google/gemini-2.5-flash-lite"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 0
    timeout_seconds: int = 60
    max_tokens: int = 512


class EmbeddingsSettings(BaseModel):
    model_config = _STRICT

    model: str = "openai/text-embedding-3-small"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: SecretStr = SecretStr("")
    vector_dim: int = 768


class PromptsSettings(BaseModel):
    model_config = _STRICT

    review_summarizer_path: str = "packages/agents/review_summarizer/prompts/prompt.md"
    letsplay_analyst_path: str = "packages/agents/letsplay_analyst/prompts/prompt.md"


class ApiSettings(BaseModel):
    model_config = _STRICT

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    command_token: SecretStr = SecretStr("")
    command_rate_limit_per_minute: int = 10
    heartbeat_stale_seconds: int = 30
    page_size_default: int = 20
    page_size_max: int = 100


class WebSettings(BaseModel):
    model_config = _STRICT

    api_base_url: str = "http://localhost:8000/api/v1"


class MonitorSettings(BaseModel):
    model_config = _STRICT

    heartbeat_stale_seconds: int = 30
    show_instance_id: bool = True
    include_scrape_circuit_state: bool = True
    include_last_parse_error: bool = True
    sse_poll_seconds: float = 2.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="GAMES_INTEL__",
        env_nested_delimiter="__",
        case_sensitive=False,
        enable_decoding=True,
    )

    app: AppSettings = Field(default_factory=AppSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    idempotency: IdempotencySettings = Field(default_factory=IdempotencySettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    reviews: ReviewsSettings = Field(default_factory=ReviewsSettings)
    letsplay: LetsPlaySettings = Field(default_factory=LetsPlaySettings)
    similarity: SimilaritySettings = Field(default_factory=SimilaritySettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    adapters: AdaptersSettings = Field(default_factory=AdaptersSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    stt: SttSettings = Field(default_factory=SttSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    prompts: PromptsSettings = Field(default_factory=PromptsSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    monitor: MonitorSettings = Field(default_factory=MonitorSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        yaml_path = os.environ.get("APP_CONFIG_PATH")
        if yaml_path:
            sources.append(
                YamlConfigSettingsSource(
                    settings_cls, yaml_file=yaml_path, yaml_file_encoding="utf-8"
                )
            )
        sources.append(dotenv_settings)
        sources.append(file_secret_settings)
        return tuple(sources)

    @model_validator(mode="after")
    def apply_topic_prefix_and_secrets(self) -> Settings:
        prefix = self.kafka.topic_prefix.strip()
        if prefix:
            events = self.kafka.events
            updates: dict[str, str] = {}
            for name in type(events).model_fields:
                current = getattr(events, name)
                if not current.startswith(prefix):
                    updates[name] = f"{prefix}{current}"
            if updates:
                object.__setattr__(self.kafka, "events", events.model_copy(update=updates))
        llm_key = self.llm.api_key.get_secret_value().strip()
        llm_base = self.llm.base_url.strip()
        embedding_updates: dict[str, Any] = {}
        stt_updates: dict[str, Any] = {}
        if llm_key:
            if not self.embeddings.api_key.get_secret_value().strip():
                embedding_updates["api_key"] = self.llm.api_key
            if not self.stt.api_key.get_secret_value().strip() and _api_origin(
                self.stt.base_url
            ) == _api_origin(self.llm.base_url):
                stt_updates["api_key"] = self.llm.api_key
        if llm_base:
            if not self.embeddings.base_url.strip():
                embedding_updates["base_url"] = llm_base
            if not self.stt.base_url.strip():
                stt_updates["base_url"] = llm_base
        if embedding_updates:
            object.__setattr__(
                self, "embeddings", self.embeddings.model_copy(update=embedding_updates)
            )
        if stt_updates:
            object.__setattr__(self, "stt", self.stt.model_copy(update=stt_updates))
        return self

    def event_name(self, key: str) -> str:
        return self.kafka.events.resolve(key)

    def consumer_group_id(self, key: str) -> str:
        return self.kafka.consumer_groups.resolve(key)


def _apply_database_url_alias() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if database_url and "GAMES_INTEL__DATABASE__URL" not in os.environ:
        os.environ["GAMES_INTEL__DATABASE__URL"] = database_url


def load_settings() -> Settings:
    _apply_database_url_alias()
    return Settings()
