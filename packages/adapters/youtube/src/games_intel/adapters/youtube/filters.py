from __future__ import annotations

import re
from collections.abc import Sequence

from games_intel.contracts.adapters import VideoHit
from games_intel.settings.config import YoutubeAdapterSettings

_NON_ALNUM = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def normalize_title(value: str) -> str:
    stripped = _NON_ALNUM.sub("", value.casefold())
    return " ".join(stripped.split())


_EDITION_TOKENS = frozenset({"edition", "complete", "deluxe", "definitive", "remastered", "remake"})


def title_match_needles(game_title: str) -> list[str]:
    """Full title plus a shorter primary name so subtitles do not drop real let's plays."""

    full = normalize_title(game_title)
    if not full:
        return []
    needles = [full]
    if ":" in game_title:
        primary = normalize_title(game_title.split(":", 1)[0])
        if primary and primary not in needles:
            needles.append(primary)
    compact = " ".join(token for token in full.split() if token not in _EDITION_TOKENS)
    if compact and compact not in needles:
        needles.append(compact)
    return needles


def filter_and_sort_letsplays(
    hits: Sequence[VideoHit],
    game_title: str,
    settings: YoutubeAdapterSettings,
) -> list[VideoHit]:
    """Relevance first, then view_count desc. Compilation/teasers never win on views."""

    needles = title_match_needles(game_title)
    if not needles:
        return []
    selected = [hit for hit in hits if _is_relevant(hit, needles, settings)]
    return sorted(selected, key=lambda hit: hit.view_count, reverse=True)


def _is_relevant(hit: VideoHit, needles: Sequence[str], settings: YoutubeAdapterSettings) -> bool:
    if hit.duration_seconds < settings.min_duration_seconds:
        return False
    if hit.duration_seconds > settings.max_duration_seconds:
        return False
    haystack = normalize_title(hit.title)
    if not any(needle in haystack for needle in needles):
        return False
    return not _matches_exclude(hit.title, settings.exclude_title_patterns)


def _matches_exclude(title: str, patterns: Sequence[str]) -> bool:
    folded = title.casefold()
    normalized = normalize_title(title)
    for pattern in patterns:
        raw = pattern.casefold().strip()
        if not raw:
            continue
        if raw in folded:
            return True
        normalized_pattern = normalize_title(pattern)
        if normalized_pattern and normalized_pattern in normalized:
            return True
    return False
