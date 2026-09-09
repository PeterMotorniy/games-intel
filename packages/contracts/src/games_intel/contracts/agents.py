from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from games_intel.contracts.adapters import ReviewSnippet
from games_intel.contracts.payloads import ReviewSummary

_STRICT = ConfigDict(extra="forbid")


class LetsPlayConclusion(BaseModel):
    model_config = _STRICT

    conclusion: str
    highlights: list[str] = Field(default_factory=list)


class ReviewSummarizerInput(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str = Field(min_length=1)
    critic: list[ReviewSnippet] = Field(default_factory=list)
    user: list[ReviewSnippet] = Field(default_factory=list)


class ReviewSummarizerOutput(BaseModel):
    model_config = _STRICT

    critic: ReviewSummary
    user: ReviewSummary


class TranscriptionInput(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str = Field(min_length=1)
    audio_ref: str = Field(min_length=1)


class TranscriptionOutput(BaseModel):
    model_config = _STRICT

    text: str
    language: str | None = None


class LetsPlayAnalystInput(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str = Field(min_length=1)
    video_title: str
    transcript_excerpt: str
