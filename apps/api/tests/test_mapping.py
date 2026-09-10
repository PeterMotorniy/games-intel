from __future__ import annotations

from games_intel.api.mapping import headline_scores
from games_intel.contracts.payloads import PlatformScore


def test_headline_scores_use_best_metascore_and_same_platform_userscore() -> None:
    metascore, userscore = headline_scores(
        [
            PlatformScore(platform_code="pc", metascore=94, userscore=7.2),
            PlatformScore(platform_code="ps5", metascore=96, userscore=7.8),
        ]
    )
    assert metascore == 96
    assert userscore == 7.8


def test_headline_scores_fall_back_to_best_userscore() -> None:
    metascore, userscore = headline_scores(
        [
            PlatformScore(platform_code="pc", metascore=None, userscore=8.1),
            PlatformScore(platform_code="ns2", metascore=None, userscore=None),
        ]
    )
    assert metascore is None
    assert userscore == 8.1
