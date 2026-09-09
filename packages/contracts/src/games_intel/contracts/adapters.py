from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from games_intel.contracts.payloads import PlatformScore, RunSource

_STRICT = ConfigDict(extra="forbid")

AdapterErrorCode = Literal[
    "not_found",
    "timeout",
    "rate_limited",
    "parse_error",
    "quota_exceeded",
    "unavailable",
    "circuit_open",
]


class ReviewSnippet(BaseModel):
    model_config = _STRICT

    author: str | None = None
    score: float | None = None
    excerpt: str
    published_at: date | None = None


class AdapterError(BaseModel):
    model_config = _STRICT

    code: AdapterErrorCode
    message: str = Field(min_length=1)


class ListNewReleasesInput(BaseModel):
    model_config = _STRICT

    limit: int = Field(default=20, ge=1)


class ListBrowsePageInput(BaseModel):
    model_config = _STRICT

    page: int = Field(ge=1)
    limit: int = Field(default=20, ge=1)


class GetGameInput(BaseModel):
    model_config = _STRICT

    slug: str = Field(min_length=1)


class GetReviewsInput(BaseModel):
    model_config = _STRICT

    slug: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1)
    max_chars: int = Field(default=8000, ge=1)


class CanaryParseInput(BaseModel):
    model_config = _STRICT

    slug: str = Field(min_length=1)


class GameListingItem(BaseModel):
    model_config = _STRICT

    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    listing_url: HttpUrl
    position: int = Field(ge=0)


class GameListing(BaseModel):
    model_config = _STRICT

    items: list[GameListingItem] = Field(default_factory=list)
    source: RunSource
    page: int | None = None


class GameDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")

    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    cover_source_url: HttpUrl | None = None
    cover_bytes: bytes | None = None
    developer: str | None = None
    publisher: str | None = None
    description: str | None = None
    video_url: HttpUrl | None = None
    platforms: list[PlatformScore] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    release_date: date | None = None


class ReviewBatch(BaseModel):
    model_config = _STRICT

    items: list[ReviewSnippet] = Field(default_factory=list)
    truncated: bool = False


class CanaryParseResult(BaseModel):
    model_config = _STRICT

    ok: bool
    error_code: AdapterErrorCode | None = None


class EmbedTextInput(BaseModel):
    model_config = _STRICT

    text: str = Field(min_length=1)


class EmbedTextResult(BaseModel):
    model_config = _STRICT

    vector: list[float] = Field(min_length=1)


class SearchLetsPlaysInput(BaseModel):
    model_config = _STRICT

    title: str = Field(min_length=1)
    max_results: int = Field(default=10, ge=1)


class VideoHit(BaseModel):
    model_config = _STRICT

    video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    view_count: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    channel_title: str | None = None
    url: HttpUrl


class LetsPlaySearch(BaseModel):
    model_config = _STRICT

    items: list[VideoHit] = Field(default_factory=list)


class GetTranscriptInput(BaseModel):
    model_config = _STRICT

    video_id: str = Field(min_length=1)
    max_chars: int = Field(ge=1)


TranscriptStatus = Literal["ok", "transcript_unavailable"]


class TranscriptResult(BaseModel):
    model_config = _STRICT

    status: TranscriptStatus
    language: str | None = None
    text: str = ""
    truncated: bool = False


class GetAudioInput(BaseModel):
    model_config = _STRICT

    video_id: str = Field(min_length=1)
    max_duration_seconds: int = Field(ge=1)


AudioStatus = Literal["ok", "unavailable"]


class AudioResult(BaseModel):
    model_config = _STRICT

    status: AudioStatus
    audio_ref: str | None = None


class TranscribeInput(BaseModel):
    model_config = _STRICT

    audio_ref: str = Field(min_length=1)


class TranscribeResult(BaseModel):
    model_config = _STRICT

    text: str
    language: str | None = None
