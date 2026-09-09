from __future__ import annotations

from datetime import date
from uuid import UUID

from games_intel.db.records import SimilarityGame
from games_intel.settings.config import SimilaritySettings
from games_intel.workers.similarity.scoring import (
    cosine_unit,
    hybrid_score,
    jaccard,
    pair_score,
    release_similarity,
    top_k,
)
from games_intel.workers.similarity.text import canonical_embedding_text, embedding_input_hash


def _game(
    slug: str,
    *,
    title: str | None = None,
    developer: str | None = "Studio",
    publisher: str | None = "Pub",
    genres: tuple[str, ...] = ("Action",),
    description: str | None = "A game.",
    critic_summary: str | None = None,
    user_summary: str | None = None,
    release_date: date | None = date(2022, 1, 1),
    platforms: tuple[str, ...] = ("ps5",),
    embedding: tuple[float, ...] | None = (1.0, 0.0),
    embedding_hash: str | None = "h",
    game_id: UUID | None = None,
) -> SimilarityGame:
    return SimilarityGame(
        id=game_id or UUID(int=abs(hash(slug)) % 10**12),
        metacritic_slug=slug,
        title=title or slug.replace("-", " ").title(),
        developer=developer,
        publisher=publisher,
        genres=genres,
        description=description,
        critic_summary=critic_summary,
        user_summary=user_summary,
        release_date=release_date,
        platform_codes=platforms,
        embedding=embedding,
        embedding_input_hash=embedding_hash,
    )


def test_canonical_text_skips_empty_and_never_inserts_na() -> None:
    game = _game(
        "elden-ring",
        title="Elden Ring",
        developer=None,
        publisher="  ",
        genres=(),
        description=None,
        critic_summary="Great combat.",
        user_summary="",
    )
    catalog_only = canonical_embedding_text(game, include_reviews=False)
    assert "n/a" not in catalog_only.lower()
    assert "developer" not in catalog_only
    assert "publisher" not in catalog_only
    assert "genres" not in catalog_only
    assert "description" not in catalog_only
    assert "critic_summary" not in catalog_only
    assert "title: Elden Ring" in catalog_only
    with_reviews = canonical_embedding_text(game, include_reviews=True)
    assert "critic_summary: Great combat." in with_reviews
    assert "user_summary" not in with_reviews


def test_same_input_same_hash() -> None:
    game = _game("elden-ring", title="Elden Ring")
    text = canonical_embedding_text(game, include_reviews=True)
    first = embedding_input_hash(text, model="nomic-embed-text", vector_dim=768)
    second = embedding_input_hash(text, model="nomic-embed-text", vector_dim=768)
    assert first == second
    other_model = embedding_input_hash(text, model="other", vector_dim=768)
    assert other_model != first


def test_cosine_clamped_and_jaccard_release() -> None:
    assert cosine_unit((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert cosine_unit((1.0, 0.0), (0.0, 1.0)) == 0.0
    assert cosine_unit((-1.0, 0.0), (1.0, 0.0)) == 0.0
    assert jaccard(("ps5", "pc"), ("pc", "ns2")) == 1 / 3
    assert jaccard((), ()) is None
    close = release_similarity(date(2022, 1, 1), date(2022, 1, 2), tau_days=365)
    far = release_similarity(date(2020, 1, 1), date(2024, 1, 1), tau_days=365)
    assert close is not None and far is not None
    assert close > far
    assert release_similarity(None, date(2022, 1, 1), tau_days=365) == 0.0


def test_hybrid_renormalizes_zero_signals() -> None:
    weights = SimilaritySettings()
    only_vector = hybrid_score(
        vector=0.5,
        platforms=None,
        genres=None,
        release=None,
        weights=weights,
    )
    assert only_vector == 0.5
    mixed = hybrid_score(
        vector=1.0,
        platforms=1.0,
        genres=None,
        release=None,
        weights=weights,
    )
    expected = (1.0 * 0.70 + 1.0 * 0.15) / (0.70 + 0.15)
    assert abs(mixed - expected) < 1e-9
    zero_vector_kept = hybrid_score(
        vector=0.0,
        platforms=1.0,
        genres=1.0,
        release=1.0,
        weights=weights,
    )
    assert abs(zero_vector_kept - 0.30) < 1e-9


def test_topk_tie_break_slug_and_excludes_self() -> None:
    weights = SimilaritySettings(k=5, w_vector=1.0, w_platform=0, w_genre=0, w_release=0)
    shared = (1.0, 0.0)
    alpha = _game("alpha", embedding=shared, game_id=UUID(int=1))
    zeta = _game("zeta", embedding=shared, game_id=UUID(int=2))
    beta = _game("beta", embedding=shared, game_id=UUID(int=3))
    ranked = top_k(alpha, (alpha, zeta, beta), weights, k=5)
    assert [item.game.metacritic_slug for item in ranked] == ["beta", "zeta"]
    assert all(item.game.metacritic_slug != "alpha" for item in ranked)
    pair = pair_score(alpha, alpha, weights)
    assert pair is None
    missing = pair_score(alpha, _game("none", embedding=None, game_id=UUID(int=9)), weights)
    assert missing is None
