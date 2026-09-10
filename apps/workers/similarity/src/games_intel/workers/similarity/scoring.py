from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from games_intel.contracts.payloads import SimilarGameRef
from games_intel.db.records import SimilarityGame, SimilarNeighbor
from games_intel.settings.config import SimilaritySettings


@dataclass(frozen=True, slots=True)
class RankedMatch:
    game: SimilarityGame
    score: float
    score_vector: float
    rank: int


def cosine_unit(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity clamped to [0, 1]. Missing/empty vectors are not scored here."""
    if len(left) != len(right) or not left:
        return 0.0
    dot = 0.0
    left_norm_sq = 0.0
    right_norm_sq = 0.0
    for a, b in zip(left, right, strict=True):
        dot += a * b
        left_norm_sq += a * a
        right_norm_sq += b * b
    if left_norm_sq == 0.0 or right_norm_sq == 0.0:
        return 0.0
    raw = dot / (math.sqrt(left_norm_sq) * math.sqrt(right_norm_sq))
    return max(0.0, min(1.0, raw))


def jaccard(left: Sequence[str], right: Sequence[str]) -> float | None:
    a = {item for item in left if item}
    b = {item for item in right if item}
    if not a and not b:
        return None
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


def release_similarity(left: date | None, right: date | None, *, tau_days: int) -> float | None:
    if left is None or right is None:
        return None
    if tau_days <= 0:
        return 0.0
    delta = abs((left - right).days)
    return math.exp(-delta / tau_days)


def hybrid_score(
    *,
    vector: float,
    platforms: float | None,
    genres: float | None,
    release: float | None,
    weights: SimilaritySettings,
) -> float:
    parts: list[tuple[float, float]] = []
    for signal, weight in (
        (vector, weights.w_vector),
        (platforms, weights.w_platform),
        (genres, weights.w_genre),
        (release, weights.w_release),
    ):
        if signal is None or weight <= 0:
            continue
        parts.append((signal, weight))
    if not parts:
        return 0.0
    total = sum(weight for _, weight in parts)
    return sum(signal * (weight / total) for signal, weight in parts)


def pair_score(
    game: SimilarityGame,
    other: SimilarityGame,
    weights: SimilaritySettings,
) -> tuple[float, float] | None:
    if game.id == other.id:
        return None
    if game.embedding is None or other.embedding is None:
        return None
    vector = cosine_unit(game.embedding, other.embedding)
    score = hybrid_score(
        vector=vector,
        platforms=jaccard(game.platform_codes, other.platform_codes),
        genres=jaccard(game.genres, other.genres),
        release=release_similarity(
            game.release_date, other.release_date, tau_days=weights.release_tau_days
        ),
        weights=weights,
    )
    return score, vector


def top_k(
    game: SimilarityGame,
    corpus: Sequence[SimilarityGame],
    weights: SimilaritySettings,
    *,
    k: int,
) -> tuple[RankedMatch, ...]:
    scored: list[tuple[float, str, SimilarityGame, float]] = []
    for other in corpus:
        pair = pair_score(game, other, weights)
        if pair is None:
            continue
        score, score_vector = pair
        scored.append((score, other.metacritic_slug, other, score_vector))
    scored.sort(key=lambda item: (-item[0], item[1]))
    limit = max(k, 0)
    ranked: list[RankedMatch] = []
    for index, (score, _slug, other, score_vector) in enumerate(scored[:limit], start=1):
        ranked.append(RankedMatch(game=other, score=score, score_vector=score_vector, rank=index))
    return tuple(ranked)


def neighbors_from_matches(matches: Sequence[RankedMatch]) -> tuple[SimilarNeighbor, ...]:
    return tuple(
        SimilarNeighbor(
            similar_game_id=item.game.id,
            score=item.score,
            rank=item.rank,
            score_vector=item.score_vector,
        )
        for item in matches
    )


def refs_from_matches(matches: Sequence[RankedMatch]) -> list[SimilarGameRef]:
    return [
        SimilarGameRef(
            metacritic_slug=item.game.metacritic_slug,
            title=item.game.title,
            score=item.score,
            rank=item.rank,
        )
        for item in matches
    ]
