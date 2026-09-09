from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal

from bs4 import BeautifulSoup, Tag

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.platforms import normalize_platform_code
from games_intel.adapters.metacritic.urls import absolute_url, game_url
from games_intel.contracts.adapters import (
    GameDetails,
    GameListing,
    GameListingItem,
    ReviewBatch,
    ReviewSnippet,
)
from games_intel.contracts.payloads import PlatformScore
from games_intel.settings.config import MetacriticAdapterSettings

_SLUG_RE = re.compile(r"/game/([a-z0-9-]+)/?(?:$|[?#])", re.IGNORECASE)
_SKIP_SLUGS = frozenset(
    {
        "browse",
        "genre",
        "platform",
        "new-releases",
        "upcoming",
        "best-games",
        "all",
    }
)
_DATE_FORMATS = (
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
)
_TBD = re.compile(r"^tbd\.?$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_CREDIT_LABEL_RE = re.compile(r"^(developer|publisher)\s*:\s*", re.IGNORECASE)
_USER_SCORE_ARIA_RE = re.compile(r"user score\s+(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_listing(
    html: str,
    settings: MetacriticAdapterSettings,
    *,
    source: Literal["new_releases", "browse"],
    page: int | None = None,
    limit: int | None = None,
) -> GameListing:
    soup = BeautifulSoup(html, "html.parser")
    container = _first_match(soup, settings.markers.listing_container)
    if container is None:
        raise MetacriticAdapterError("parse_error", "listing container marker missing")
    title_selector = settings.markers.listing_section_title
    if title_selector.strip() and _first_match(container, title_selector) is None:
        if _first_match(soup, title_selector) is None:
            raise MetacriticAdapterError("parse_error", "listing section title marker missing")
    cards = _select(container, settings.selectors.listing.game_card)
    if not cards:
        cards = _select(soup, settings.selectors.listing.game_card)
    items: list[GameListingItem] = []
    for card in cards:
        item = _parse_listing_card(card, settings)
        if item is not None:
            items.append(
                GameListingItem(
                    slug=item[0],
                    title=item[1],
                    listing_url=item[2],  # type: ignore[arg-type]
                    position=len(items),
                )
            )
    if not items and cards:
        raise MetacriticAdapterError("parse_error", "listing cards present but no valid slugs")
    min_cards = max(0, settings.markers.listing_min_cards)
    if min_cards > 1 and len(cards) >= min_cards and len(items) < min_cards:
        raise MetacriticAdapterError(
            "parse_error",
            f"listing parsed {len(items)} games, expected at least {min_cards}",
        )
    if limit is not None:
        items = items[:limit]
        for index, current in enumerate(items):
            items[index] = current.model_copy(update={"position": index})
    return GameListing(items=items, source=source, page=page)


def parse_game(html: str, settings: MetacriticAdapterSettings, slug: str) -> GameDetails:
    soup = BeautifulSoup(html, "html.parser")
    container = _first_match(soup, settings.markers.card_container)
    if container is None:
        raise MetacriticAdapterError("parse_error", "card container marker missing")
    title = _first_text(
        _first_match(container, settings.selectors.card.title) or soup.select_one("h1")
    )
    if not title:
        raise MetacriticAdapterError("parse_error", "game title missing")
    cover = _cover_url(container, settings)
    developer = _credit_text(container, settings.selectors.card.developer)
    publisher = _credit_text(container, settings.selectors.card.publisher)
    if not developer:
        developer = _credit_text(soup, settings.selectors.card.developer)
    if not publisher:
        publisher = _credit_text(soup, settings.selectors.card.publisher)
    description = _optional_text(container, settings.selectors.card.description) or _optional_text(
        soup, settings.selectors.card.description
    )
    video = _video_url(container, settings) or _video_url(soup, settings)
    platforms = _parse_platforms(soup, settings)
    genres = _parse_genres(soup, settings)
    release = _parse_date(_optional_text(soup, settings.selectors.card.release_date))
    details = GameDetails(
        slug=slug,
        title=title,
        cover_source_url=cover,  # type: ignore[arg-type]
        developer=developer,
        publisher=publisher,
        description=description,
        video_url=video,  # type: ignore[arg-type]
        platforms=platforms,
        genres=genres,
        release_date=release,
    )
    return _enrich_game_from_json_ld(details, soup, settings)


def parse_reviews(
    html: str,
    settings: MetacriticAdapterSettings,
    *,
    kind: Literal["critic", "user"],
    limit: int,
    max_chars: int,
) -> ReviewBatch:
    soup = BeautifulSoup(html, "html.parser")
    container = _first_match(soup, settings.markers.reviews_container)
    if container is None:
        raise MetacriticAdapterError("parse_error", "reviews container marker missing")
    selector = (
        settings.selectors.reviews.critic_item
        if kind == "critic"
        else settings.selectors.reviews.user_item
    )
    nodes = _select(soup, selector)
    if not nodes:
        nodes = _select(container, selector)
    snippets: list[ReviewSnippet] = []
    for node in nodes:
        snippet = _parse_review_item(node, settings)
        if snippet is not None:
            snippets.append(snippet)
    if nodes and not snippets:
        raise MetacriticAdapterError("parse_error", "review nodes present but no valid snippets")
    return clip_review_batch(snippets, limit=limit, max_chars=max_chars)


def clip_review_batch(
    items: Sequence[ReviewSnippet],
    *,
    limit: int,
    max_chars: int,
    already_truncated: bool = False,
) -> ReviewBatch:
    clipped: list[ReviewSnippet] = []
    used_chars = 0
    truncated = already_truncated
    for index, snippet in enumerate(items):
        if len(clipped) >= limit:
            truncated = True
            break
        remaining = max_chars - used_chars
        if remaining <= 0:
            truncated = True
            break
        excerpt = snippet.excerpt
        if len(excerpt) > remaining:
            excerpt = excerpt[:remaining]
            truncated = True
        clipped.append(snippet.model_copy(update={"excerpt": excerpt}))
        used_chars += len(excerpt)
        if index + 1 < len(items) and len(clipped) >= limit:
            truncated = True
    if len(items) > limit:
        truncated = True
    return ReviewBatch(items=clipped, truncated=truncated)


def _parse_listing_card(
    card: Tag, settings: MetacriticAdapterSettings
) -> tuple[str, str, str] | None:
    link = _first_match(card, settings.selectors.listing.slug)
    href = _attr(link, "href") if link is not None else ""
    slug = slug_from_href(href)
    if slug is None:
        return None
    title_node = _first_match(card, settings.selectors.listing.title)
    title = (
        _first_text(title_node) or _first_text(link) or _attr(_first_match(card, "img[alt]"), "alt")
    )
    if not title:
        return None
    listing = absolute_url(settings.base_url, href) if href else game_url(settings.base_url, slug)
    return slug, title, listing


def _parse_platforms(root: Tag, settings: MetacriticAdapterSettings) -> list[PlatformScore]:
    nodes = _select(root, settings.selectors.card.platforms)
    scores: list[PlatformScore] = []
    seen: set[str] = set()
    for node in nodes:
        code = _platform_code_from_node(node, settings)
        if not code or code == "unknown" or code in seen:
            continue
        meta_node = _first_match(node, settings.selectors.card.metascore)
        user_node = _first_match(node, settings.selectors.card.userscore)
        seen.add(code)
        scores.append(
            PlatformScore(
                platform_code=code,
                metascore=_parse_int_score(_first_text(meta_node)),
                userscore=_parse_float_score(_first_text(user_node)),
            )
        )
    return _apply_hero_userscore(scores, root)


_PLATFORM_QUERY_RE = re.compile(r"[?&]platform=([a-z0-9-]+)", re.IGNORECASE)


def _platform_code_from_node(node: Tag, settings: MetacriticAdapterSettings) -> str:
    data = _attr(node, "data-platform")
    if data:
        return normalize_platform_code(data)
    href = _attr(node, "href") or _attr(node, "to")
    query = _PLATFORM_QUERY_RE.search(href)
    if query is not None:
        return normalize_platform_code(query.group(1))
    titled = node.select_one("[title]")
    title = _attr(titled, "title") if titled is not None else ""
    if title:
        code = normalize_platform_code(title)
        if code and code != "unknown":
            return code
    code_node = _first_match(node, settings.selectors.card.platform_code)
    raw = _first_text(code_node)
    if not raw:
        return ""
    code = normalize_platform_code(raw)
    if code == "unknown" or len(code) > 24:
        return ""
    return code


def _credit_text(root: Tag | BeautifulSoup, selector: str) -> str | None:
    raw = _optional_text(root, selector)
    cleaned = _CREDIT_LABEL_RE.sub("", raw).strip()
    return cleaned or None


def _parse_hero_user_score(root: Tag) -> float | None:
    for block in _select(root, '[data-testid="product-score"]'):
        header = _first_text(_first_match(block, '[data-testid="global-score-header"]'))
        if header.casefold() != "user score":
            continue
        wrapper = _first_match(block, '[data-testid="global-score-value-wrapper"]')
        aria = _attr(wrapper, "aria-label") or _attr(wrapper, "title")
        match = _USER_SCORE_ARIA_RE.search(aria)
        if match is not None:
            return _parse_float_score(match.group(1))
        return _parse_float_score(
            _first_text(_first_match(block, '[data-testid="global-score-value"]'))
        )
    return None


def _selected_platform_code(root: Tag) -> str:
    logo = root.select_one('[data-testid="platform-selector"] [title]')
    titled = _attr(logo, "title") if isinstance(logo, Tag) else ""
    if titled:
        code = normalize_platform_code(titled)
        if code and code != "unknown":
            return code
    for card in _select(root, '[data-testid="product-score-card"]'):
        href = _attr(card, "href") or _attr(card, "to")
        query = _PLATFORM_QUERY_RE.search(href)
        if query is not None:
            code = normalize_platform_code(query.group(1))
            if code and code != "unknown":
                return code
    return ""


def _apply_hero_userscore(scores: list[PlatformScore], root: Tag) -> list[PlatformScore]:
    hero_user = _parse_hero_user_score(root)
    if hero_user is None or not scores:
        return scores
    selected = _selected_platform_code(root)
    if selected:
        for index, row in enumerate(scores):
            if row.platform_code == selected:
                if row.userscore is None:
                    scores[index] = row.model_copy(update={"userscore": hero_user})
                return scores
    scored = [index for index, row in enumerate(scores) if row.metascore is not None]
    if len(scored) == 1:
        index = scored[0]
        if scores[index].userscore is None:
            scores[index] = scores[index].model_copy(update={"userscore": hero_user})
    return scores


def _parse_genres(root: Tag, settings: MetacriticAdapterSettings) -> list[str]:
    nodes = _select(root, settings.selectors.card.genres)
    genres: list[str] = []
    for node in nodes:
        for part in re.split(r"[,/|]", _first_text(node)):
            label = part.strip().lower()
            if label and label not in genres:
                genres.append(label)
    return genres


def _review_author(
    node: Tag, settings: MetacriticAdapterSettings, score: float | None
) -> str | None:
    raw = _plain_text(_first_match(node, settings.selectors.reviews.author))
    if not raw:
        return None
    if score is None:
        return raw
    score_token = str(int(score)) if score.is_integer() else str(score)
    if raw.startswith(score_token):
        stripped = raw[len(score_token) :].strip()
        return stripped or None
    return raw


def _parse_review_item(node: Tag, settings: MetacriticAdapterSettings) -> ReviewSnippet | None:
    body = _plain_text(_first_match(node, settings.selectors.reviews.body)) or _plain_text(node)
    if not body:
        return None
    score_text = _plain_text(_first_match(node, settings.selectors.reviews.score))
    score = _parse_float_score(score_text)
    author = _review_author(node, settings, score)
    return ReviewSnippet(
        author=author,
        score=score,
        excerpt=body,
        published_at=None,
    )


def _cover_url(root: Tag, settings: MetacriticAdapterSettings) -> str | None:
    node = _first_match(root, settings.selectors.card.cover)
    if node is None:
        return None
    src = _attr(node, "src") or _srcset_first(_attr(node, "srcset"))
    if not src:
        return None
    return absolute_url(settings.base_url, src)


def _video_url(root: Tag, settings: MetacriticAdapterSettings) -> str | None:
    node = _first_match(root, settings.selectors.card.video)
    if node is None:
        return None
    href = _attr(node, "src") or _attr(node, "href") or _attr(node, "data-src")
    if not href:
        return None
    absolute = absolute_url(settings.base_url, href)
    if absolute.startswith(("http://", "https://")):
        return absolute
    return None


def slug_from_href(href: str) -> str | None:
    if not href:
        return None
    match = _SLUG_RE.search(href)
    if match is None:
        return None
    slug = match.group(1).lower()
    if slug in _SKIP_SLUGS:
        return None
    return slug


def _parse_int_score(text: str) -> int | None:
    if not text or _TBD.match(text.strip()):
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _parse_float_score(text: str) -> float | None:
    if not text or _TBD.match(text.strip()):
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    if not text:
        return None
    cleaned = " ".join(text.replace("Released On:", "").replace("Released:", "").split())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _first_match(root: Tag | BeautifulSoup, selector: str) -> Tag | None:
    matches = _select(root, selector)
    return matches[0] if matches else None


def _select(root: Tag | BeautifulSoup, selector: str) -> list[Tag]:
    if not selector.strip():
        return []
    found: list[Tag] = []
    for element in root.select(selector):
        if isinstance(element, Tag):
            found.append(element)
    return found


def _first_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _plain_text(node: Tag | None) -> str:
    if node is None:
        return ""
    raw = html.unescape(node.get_text(" ", strip=True))
    stripped = _HTML_TAG_RE.sub("", raw)
    return " ".join(stripped.split())


def _optional_text(root: Tag | BeautifulSoup, selector: str) -> str:
    return _first_text(_first_match(root, selector))


def _attr(node: Tag | None, name: str) -> str:
    if node is None:
        return ""
    value = node.get(name)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    if value is None:
        return ""
    return str(value).strip()


def _srcset_first(srcset: str) -> str:
    if not srcset:
        return ""
    first = srcset.split(",")[0].strip().split(" ")[0]
    return first


def _enrich_game_from_json_ld(
    details: GameDetails, soup: BeautifulSoup, settings: MetacriticAdapterSettings
) -> GameDetails:
    payload = _json_ld_videogame(soup)
    if payload is None:
        return details
    title = details.title
    ld_name = payload.get("name")
    if isinstance(ld_name, str) and ld_name.strip() and not title:
        title = ld_name.strip()
    cover = str(details.cover_source_url) if details.cover_source_url else ""
    ld_cover = _json_ld_image_url(payload.get("image"), settings)
    if ld_cover and (not cover or _looks_like_trailer_asset(cover)):
        cover = ld_cover
    video = str(details.video_url) if details.video_url else ""
    ld_video = _json_ld_trailer_url(payload.get("trailer"))
    if ld_video and not video:
        video = ld_video
    description = details.description or ""
    ld_description = payload.get("description")
    if isinstance(ld_description, str) and ld_description.strip():
        if not description or _looks_like_noisy_summary(description):
            description = " ".join(ld_description.split())
    publisher = details.publisher
    if not publisher:
        publisher = _json_ld_publisher_name(payload.get("publisher"), details.developer)
    genres = details.genres
    if not genres:
        genres = _json_ld_genres(payload.get("genre"))
    release = details.release_date
    if release is None:
        raw_date = payload.get("datePublished") or payload.get("dateCreated")
        if isinstance(raw_date, str):
            release = _parse_date(raw_date[:10]) or _parse_date(raw_date)
    return details.model_copy(
        update={
            "title": title,
            "cover_source_url": cover or None,
            "video_url": video or None,
            "description": description or None,
            "publisher": publisher,
            "genres": genres,
            "release_date": release,
        }
    )


def _json_ld_videogame(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or ""
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, Mapping) and item.get("@type") == "VideoGame":
                return dict(item)
    return None


def _json_ld_image_url(value: Any, settings: MetacriticAdapterSettings) -> str | None:
    url = ""
    if isinstance(value, str):
        url = value
    elif isinstance(value, Mapping):
        raw = value.get("url") or value.get("contentUrl")
        if isinstance(raw, str):
            url = raw
    elif isinstance(value, list) and value:
        return _json_ld_image_url(value[0], settings)
    if not url:
        return None
    return absolute_url(settings.base_url, url)


def _json_ld_trailer_url(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("embedUrl", "contentUrl", "url"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.startswith(("http://", "https://")):
            return raw
    return None


def _json_ld_publisher_name(value: Any, developer: str | None) -> str | None:
    names: list[str] = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        name = ""
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, Mapping):
            raw = item.get("name")
            if isinstance(raw, str):
                name = raw.strip()
        if name and name not in names:
            names.append(name)
    developer_norm = (developer or "").casefold()
    for name in names:
        if name.casefold() != developer_norm:
            return name
    return names[0] if names else None


def _json_ld_genres(value: Any) -> list[str]:
    raw_items: list[str] = []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = [item for item in value if isinstance(item, str)]
    genres: list[str] = []
    for item in raw_items:
        for part in re.split(r"[,/|]", item):
            label = part.strip().lower()
            if label and label not in genres:
                genres.append(label)
    return genres


def _looks_like_trailer_asset(url: str) -> bool:
    lowered = url.casefold()
    return "jwplayer.com" in lowered or "/poster.jpg" in lowered


def _looks_like_noisy_summary(text: str) -> bool:
    lowered = text.casefold()
    return "read more" in lowered or lowered.startswith("summary ")
