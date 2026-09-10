from __future__ import annotations

from games_intel.adapters.metacritic.urls import is_allowed_fetch_url, listing_source_for_url

BASE = "https://www.metacritic.com"


def test_allows_configured_origin_and_metacritic_cdn() -> None:
    assert is_allowed_fetch_url("https://www.metacritic.com/game/elden-ring/", BASE)
    assert is_allowed_fetch_url("https://static.metacritic.com/images/x.jpg", BASE)
    assert is_allowed_fetch_url("http://www.metacritic.com/game/x/", BASE)


def test_rejects_ssrf_and_userinfo() -> None:
    assert is_allowed_fetch_url("http://127.0.0.1/latest", BASE) is False
    assert is_allowed_fetch_url("https://evil.example/cover.jpg", BASE) is False
    assert is_allowed_fetch_url("https://user:pass@www.metacritic.com/x", BASE) is False
    assert is_allowed_fetch_url("file:///etc/passwd", BASE) is False
    assert is_allowed_fetch_url("https://metacritic.com.evil.example/x", BASE) is False


def test_listing_source_for_url_distinguishes_browse_home_and_card() -> None:
    browse = "/browse/game/all/all/all-time/new/"
    home = "/game/"
    kwargs = {"browse_path": browse, "new_releases_path": home}
    assert listing_source_for_url(f"{BASE}/game/", **kwargs) == "new_releases"
    assert listing_source_for_url(f"{BASE}/", **kwargs) == "new_releases"
    assert listing_source_for_url(f"{BASE}{browse}?page=2", **kwargs) == "browse"
    assert listing_source_for_url(f"{BASE}/game/elden-ring/", **kwargs) is None
    assert listing_source_for_url(f"{BASE}/game/elden-ring/critic-reviews/", **kwargs) is None
