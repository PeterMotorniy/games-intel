from __future__ import annotations

from typing import Literal
from urllib.parse import urljoin, urlparse, urlunparse


def join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def game_url(base_url: str, slug: str) -> str:
    return join_url(base_url, f"/game/{slug}/")


def critic_reviews_url(base_url: str, slug: str) -> str:
    return join_url(base_url, f"/game/{slug}/critic-reviews/")


def user_reviews_url(base_url: str, slug: str) -> str:
    return join_url(base_url, f"/game/{slug}/user-reviews/")


def listing_source_for_url(
    url: str, *, browse_path: str, new_releases_path: str
) -> Literal["new_releases", "browse"] | None:
    path = urlparse(url).path or "/"
    current = path.rstrip("/") or "/"
    browse = _normalize_path(browse_path).rstrip("/")
    if browse and (current == browse or current.startswith(f"{browse}/")):
        return "browse"
    home = _normalize_path(new_releases_path).rstrip("/") or "/"
    if current in {home, "/"}:
        return "new_releases"
    return None


def _normalize_path(path: str) -> str:
    cleaned = path.strip() or "/"
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def browse_url(base_url: str, browse_path: str, page_param: str, page: int) -> str:
    path = browse_path
    if "?" in path:
        separator = "&"
    else:
        separator = "?"
    if page_param:
        return join_url(base_url, f"{path}{separator}{page_param}={page}")
    return join_url(base_url, path)


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def is_allowed_fetch_url(url: str, base_url: str) -> bool:
    """Allow only http(s) URLs on the configured Metacritic origin or *.metacritic.com."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").casefold()
    if not host:
        return False
    base_host = (urlparse(base_url).hostname or "").casefold()
    if base_host and host == base_host:
        return True
    return host == "metacritic.com" or host.endswith(".metacritic.com")


def absolute_url(base_url: str, maybe_relative: str) -> str:
    if maybe_relative.startswith(("http://", "https://")):
        return maybe_relative
    return urljoin(base_url.rstrip("/") + "/", maybe_relative)
