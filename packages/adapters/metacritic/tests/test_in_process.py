from __future__ import annotations

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.factory import create_metacritic_port
from games_intel.adapters.metacritic.in_process import InProcessMetacriticAdapter
from games_intel.contracts.adapters import (
    GetReviewsInput,
    ListNewReleasesInput,
    ReviewBatch,
    ReviewSnippet,
)
from games_intel.settings import Settings


def test_in_process_mode_does_not_use_sidecar() -> None:
    settings = Settings().model_copy(
        update={
            "adapters": Settings().adapters.model_copy(
                update={
                    "metacritic": Settings().adapters.metacritic.model_copy(
                        update={"mode": "in_process"}
                    )
                }
            )
        }
    )
    port = create_metacritic_port(settings)
    assert isinstance(port, InProcessMetacriticAdapter)


async def test_in_process_raises_when_unconfigured() -> None:
    adapter = InProcessMetacriticAdapter()
    try:
        await adapter.list_new_releases(ListNewReleasesInput(limit=20))
    except MetacriticAdapterError as exc:
        assert exc.code == "unavailable"
    else:
        raise AssertionError("expected unavailable")


async def test_in_process_clips_reviews_to_limit() -> None:
    batch = ReviewBatch(
        items=[
            ReviewSnippet(author="a", score=1, excerpt="one"),
            ReviewSnippet(author="b", score=2, excerpt="two"),
        ],
        truncated=False,
    )
    adapter = InProcessMetacriticAdapter(critic_reviews={"elden-ring": batch})
    clipped = await adapter.get_critic_reviews(
        GetReviewsInput(slug="elden-ring", limit=1, max_chars=8000)
    )
    assert len(clipped.items) == 1
    assert clipped.items[0].excerpt == "one"
    assert clipped.truncated is True
