from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from games_intel.settings.config import EmbeddingsSettings

VECTOR_DIM = int(EmbeddingsSettings.model_fields["vector_dim"].default)


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "letsplay_status IS NULL OR letsplay_status IN"
            " ('ok', 'no_video', 'transcript_unavailable', 'quota_exceeded')",
            name="ck_games_letsplay_status",
        ),
        Index(
            "ix_games_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_games_genres_gin", "genres", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    metacritic_slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    listing_url: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    cover_source_url: Mapped[str | None] = mapped_column(Text)
    developer: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    release_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(Text)
    critic_likes: Mapped[list[str] | None] = mapped_column(JSONB)
    critic_dislikes: Mapped[list[str] | None] = mapped_column(JSONB)
    critic_summary: Mapped[str | None] = mapped_column(Text)
    user_likes: Mapped[list[str] | None] = mapped_column(JSONB)
    user_dislikes: Mapped[list[str] | None] = mapped_column(JSONB)
    user_summary: Mapped[str | None] = mapped_column(Text)
    letsplay_status: Mapped[str | None] = mapped_column(Text)
    letsplay_video_url: Mapped[str | None] = mapped_column(Text)
    letsplay_video_title: Mapped[str | None] = mapped_column(Text)
    letsplay_view_count: Mapped[int | None] = mapped_column(Integer)
    letsplay_conclusion: Mapped[str | None] = mapped_column(Text)
    letsplay_highlights: Mapped[list[str] | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIM))
    embedding_input_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    platforms: Mapped[list[GamePlatform]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GamePlatform(Base):
    __tablename__ = "game_platforms"
    __table_args__ = (Index("ix_game_platforms_platform_code", "platform_code"),)

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    platform_code: Mapped[str] = mapped_column(Text, primary_key=True)
    metascore: Mapped[int | None] = mapped_column(Integer)
    userscore: Mapped[Decimal | None] = mapped_column(Numeric)

    game: Mapped[Game] = relationship(back_populates="platforms")


class SimilarGame(Base):
    __tablename__ = "similar_games"
    __table_args__ = (
        CheckConstraint("game_id <> similar_game_id", name="ck_similar_games_no_self"),
        Index("ix_similar_games_similar_game_id", "similar_game_id"),
        UniqueConstraint("game_id", "rank", name="uq_similar_games_game_rank"),
    )

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    similar_game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Double, nullable=False)
    score_vector: Mapped[float | None] = mapped_column(Double)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)


class IngestionCursor(Base):
    __tablename__ = "ingestion_cursors"

    process_date: Mapped[date] = mapped_column(Date, primary_key=True)
    new_releases_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_browse_page: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'running', 'completed', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        Index(
            "uq_ingestion_runs_inflight_page",
            "process_date",
            "source",
            "page",
            unique=True,
            postgresql_where=text("status IN ('requested', 'running') AND page IS NOT NULL"),
        ),
        Index(
            "uq_ingestion_runs_inflight_null_page",
            "process_date",
            "source",
            unique=True,
            postgresql_where=text("status IN ('requested', 'running') AND page IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    process_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    limit: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionItem(Base):
    __tablename__ = "ingestion_items"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "metacritic_slug",
            "stage",
            name="uq_ingestion_items_run_slug_stage",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'degraded')",
            name="ck_ingestion_items_status",
        ),
        CheckConstraint(
            "stage IN ('discovered', 'cataloged', 'reviews', 'letsplay', 'similar')",
            name="ck_ingestion_items_stage",
        ),
        Index("ix_ingestion_items_process_date", "process_date"),
        Index("ix_ingestion_items_slug_stage_updated", "metacritic_slug", "stage", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[UUID | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"))
    metacritic_slug: Mapped[str] = mapped_column(Text, nullable=False)
    process_date: Mapped[date] = mapped_column(Date, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_type: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[str | None] = mapped_column(Text)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DailyProcessedSlug(Base):
    __tablename__ = "daily_processed_slugs"

    process_date: Mapped[date] = mapped_column(Date, primary_key=True)
    metacritic_slug: Mapped[str] = mapped_column(Text, primary_key=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (
        UniqueConstraint(
            "worker_type",
            "idempotency_key",
            name="uq_processed_events_worker_idempotency_key",
        ),
    )

    worker_type: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index(
            "ix_outbox_unpublished_producer",
            "producer",
            "id",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    producer: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    partition_key: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_type: Mapped[str] = mapped_column(Text, primary_key=True)
    instance_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_subject: Mapped[str | None] = mapped_column(Text)
    processed_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lag_hint: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExternalPageCache(Base):
    __tablename__ = "external_page_cache"

    url_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)


class AdapterHealth(Base):
    __tablename__ = "adapter_health"

    adapter_name: Mapped[str] = mapped_column(Text, primary_key=True)
    circuit_state: Mapped[str] = mapped_column(Text, nullable=False)
    parse_error_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_parse_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
