from __future__ import annotations

from pydantic import HttpUrl

from games_intel.adapters.youtube.filters import filter_and_sort_letsplays
from games_intel.contracts.adapters import VideoHit
from games_intel.settings.config import YoutubeAdapterSettings


def _hit(
    *,
    video_id: str,
    title: str,
    view_count: int,
    duration_seconds: int,
) -> VideoHit:
    return VideoHit(
        video_id=video_id,
        title=title,
        view_count=view_count,
        duration_seconds=duration_seconds,
        channel_title="Fixture Channel",
        url=HttpUrl(f"https://www.youtube.com/watch?v={video_id}"),
    )


def _settings() -> YoutubeAdapterSettings:
    return YoutubeAdapterSettings(
        min_duration_seconds=180,
        max_duration_seconds=7200,
        exclude_title_patterns=["compilation", "top 10"],
    )


def test_compilation_with_huge_views_is_dropped() -> None:
    hits = [
        _hit(
            video_id="comp",
            title="Elden Ring Compilation — Best Moments",
            view_count=99_000_000,
            duration_seconds=3600,
        ),
        _hit(
            video_id="lp",
            title="Elden Ring Let's Play Episode 1",
            view_count=12_000,
            duration_seconds=2400,
        ),
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring", _settings())
    assert [item.video_id for item in selected] == ["lp"]


def test_top10_pattern_excluded() -> None:
    hits = [
        _hit(
            video_id="top",
            title="Top 10 Elden Ring Bosses",
            view_count=5_000_000,
            duration_seconds=1200,
        )
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring", _settings())
    assert selected == []


def test_short_teaser_below_min_duration_excluded() -> None:
    hits = [
        _hit(
            video_id="teaser",
            title="Elden Ring Let's Play Trailer",
            view_count=8_000_000,
            duration_seconds=90,
        )
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring", _settings())
    assert selected == []


def test_title_must_contain_normalized_game_title() -> None:
    hits = [
        _hit(
            video_id="other",
            title="Dark Souls Let's Play",
            view_count=1_000_000,
            duration_seconds=1800,
        )
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring", _settings())
    assert selected == []


def test_sort_by_view_count_after_relevance() -> None:
    hits = [
        _hit(
            video_id="low",
            title="Elden Ring Let's Play quiet stream",
            view_count=100,
            duration_seconds=2000,
        ),
        _hit(
            video_id="high",
            title="Elden Ring Let's Play popular",
            view_count=50_000,
            duration_seconds=2000,
        ),
        _hit(
            video_id="mid",
            title="Elden Ring Let's Play mid",
            view_count=9_000,
            duration_seconds=2000,
        ),
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring", _settings())
    assert [item.video_id for item in selected] == ["high", "mid", "low"]


def test_empty_hits_valid() -> None:
    assert filter_and_sort_letsplays([], "Elden Ring", _settings()) == []


def test_subtitle_in_game_title_still_matches_core_name() -> None:
    hits = [
        _hit(
            video_id="lp",
            title="Elden Ring Let's Play Episode 1",
            view_count=12_000,
            duration_seconds=2400,
        )
    ]
    selected = filter_and_sort_letsplays(hits, "Elden Ring: Tarnished Edition", _settings())
    assert [item.video_id for item in selected] == ["lp"]


def test_punctuation_in_game_title_still_matches() -> None:
    hits = [
        _hit(
            video_id="sm",
            title="Marvel's Spider-Man 2 Let's Play",
            view_count=1000,
            duration_seconds=2000,
        )
    ]
    selected = filter_and_sort_letsplays(hits, "Marvel's Spider-Man 2", _settings())
    assert [item.video_id for item in selected] == ["sm"]
