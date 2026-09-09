from __future__ import annotations

from pathlib import Path

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.parser import parse_game, parse_listing, parse_reviews
from games_intel.adapters.metacritic.platforms import normalize_platform_code
from games_intel.settings import Settings
from games_intel.settings.config import MetacriticAdapterSettings

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "metacritic"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _settings() -> Settings:
    return Settings()


def test_new_releases_fixture_parses() -> None:
    listing = parse_listing(
        _html("new_releases.html"),
        _settings().adapters.metacritic,
        source="new_releases",
        limit=20,
    )
    slugs = [item.slug for item in listing.items]
    assert slugs == [
        "halloween-the-game",
        "onimusha-way-of-the-sword",
        "elden-ring-tarnished-edition",
    ]
    assert listing.items[0].title == "Halloween: The Game"
    assert str(listing.items[0].listing_url).endswith("/game/halloween-the-game/")
    assert listing.source == "new_releases"


def test_browse_fixture_parses() -> None:
    listing = parse_listing(
        _html("browse.html"),
        _settings().adapters.metacritic,
        source="browse",
        page=1,
        limit=20,
    )
    assert [item.slug for item in listing.items] == [
        "cat-me-if-you-can",
        "honeycomb-the-world-beyond",
    ]
    assert listing.page == 1
    assert listing.source == "browse"


def test_empty_dom_is_parse_error() -> None:
    try:
        parse_listing(
            _html("empty_dom.html"),
            _settings().adapters.metacritic,
            source="new_releases",
        )
    except MetacriticAdapterError as exc:
        assert exc.code == "parse_error"
    else:
        raise AssertionError("expected parse_error")


def test_markers_present_zero_games_is_empty_success() -> None:
    listing = parse_listing(
        _html("empty_listing.html"),
        _settings().adapters.metacritic,
        source="new_releases",
    )
    assert listing.items == []


def test_all_cards_without_slug_is_parse_error() -> None:
    html = """
    <section class="c-pageProductHome">
      <h2 class="c-sectionHeader_title">New Releases</h2>
      <div class="c-productCard"><h3 class="c-productCard_title">Nope</h3></div>
    </section>
    """
    try:
        parse_listing(html, _settings().adapters.metacritic, source="new_releases")
    except MetacriticAdapterError as exc:
        assert exc.code == "parse_error"
    else:
        raise AssertionError("expected parse_error")


def _metacritic_with_min_cards(min_cards: int) -> MetacriticAdapterSettings:
    base = _settings().adapters.metacritic
    return base.model_copy(
        update={"markers": base.markers.model_copy(update={"listing_min_cards": min_cards})}
    )


def test_partial_listing_below_min_cards_is_parse_error() -> None:
    html = """
    <section class="c-pageProductHome">
      <h2 class="c-sectionHeader_title">New Releases</h2>
      <div class="c-productCard">
        <a href="/game/valid-game/">Valid Game</a>
        <h3 class="c-productCard_title">Valid Game</h3>
      </div>
      <div class="c-productCard"><h3 class="c-productCard_title">Nope</h3></div>
      <div class="c-productCard"><h3 class="c-productCard_title">Also</h3></div>
    </section>
    """
    try:
        parse_listing(html, _metacritic_with_min_cards(3), source="new_releases")
    except MetacriticAdapterError as exc:
        assert exc.code == "parse_error"
    else:
        raise AssertionError("expected parse_error")


def test_last_page_fewer_cards_than_min_is_success() -> None:
    html = """
    <section class="c-pageProductHome">
      <h2 class="c-sectionHeader_title">New Releases</h2>
      <div class="c-productCard">
        <a href="/game/alpha-quest/">Alpha Quest</a>
        <h3 class="c-productCard_title">Alpha Quest</h3>
      </div>
      <div class="c-productCard">
        <a href="/game/beta-quest/">Beta Quest</a>
        <h3 class="c-productCard_title">Beta Quest</h3>
      </div>
    </section>
    """
    listing = parse_listing(html, _metacritic_with_min_cards(8), source="new_releases")
    assert [item.slug for item in listing.items] == ["alpha-quest", "beta-quest"]


def test_card_fixture_parses_details_and_tbd() -> None:
    details = parse_game(_html("card.html"), _settings().adapters.metacritic, "elden-ring")
    assert details.title == "Elden Ring"
    assert details.developer == "FromSoftware"
    assert details.publisher == "Bandai Namco Games"
    assert details.release_date is not None
    assert details.release_date.isoformat() == "2022-02-25"
    assert details.genres == ["action", "rpg"]
    assert details.cover_source_url is not None
    assert "elden-ring.jpg" in str(details.cover_source_url)
    assert details.video_url is not None
    by_code = {row.platform_code: row for row in details.platforms}
    assert by_code["ps5"].metascore == 96
    assert by_code["ps5"].userscore == 8.4
    assert by_code["xboxone"].metascore is None
    assert by_code["xboxone"].userscore is None
    assert by_code["ns2"].metascore is None
    assert "pc" in by_code


def test_reviews_fixture_parses() -> None:
    settings = _settings().adapters.metacritic
    critics = parse_reviews(
        _html("reviews.html"), settings, kind="critic", limit=50, max_chars=8000
    )
    users = parse_reviews(_html("reviews.html"), settings, kind="user", limit=50, max_chars=8000)
    assert len(critics.items) == 2
    assert critics.items[0].author == "IGN"
    assert critics.items[0].score == 95
    assert "<" not in critics.items[0].excerpt
    assert len(users.items) == 1
    assert users.items[0].author == "TarnishedFan"


def test_reviews_odyssey_card_strips_score_from_author() -> None:
    html = """
    <section data-testid="product-reviews">
      <article data-testid="review-card">
        <a data-testid="review-card-header" href="/publication/ign/">
          <div class="c-siteReviewScore" aria-label="Metascore 100 out of 100">
            <span>100</span>
          </div>
          IGN
        </a>
        <div data-testid="review-quote-text">Valheim is a survival crafting adventure.</div>
      </article>
    </section>
    """
    batch = parse_reviews(
        html, _settings().adapters.metacritic, kind="critic", limit=10, max_chars=8000
    )
    assert len(batch.items) == 1
    assert batch.items[0].author == "IGN"
    assert batch.items[0].score == 100
    assert "survival" in batch.items[0].excerpt


def test_reviews_strip_html_from_excerpts() -> None:
    html = """
    <section class="c-pageProductReviews" data-gi-reviews>
      <article class="c-siteReview_critic">
        <div class="c-siteReview_author"><b>IGN</b></div>
        <p class="c-siteReview_quote">Great <em>combat</em> and a <span>vast</span> world.</p>
      </article>
    </section>
    """
    batch = parse_reviews(
        html, _settings().adapters.metacritic, kind="critic", limit=10, max_chars=8000
    )
    assert len(batch.items) == 1
    assert batch.items[0].author == "IGN"
    assert batch.items[0].excerpt == "Great combat and a vast world."
    assert "<" not in batch.items[0].excerpt
    assert "</" not in batch.items[0].excerpt


def test_reviews_limit_sets_truncated() -> None:
    batch = parse_reviews(
        _html("reviews.html"),
        _settings().adapters.metacritic,
        kind="critic",
        limit=1,
        max_chars=8000,
    )
    assert len(batch.items) == 1
    assert batch.items[0].author == "IGN"
    assert batch.truncated is True


def test_reviews_max_chars_truncates() -> None:
    batch = parse_reviews(
        _html("reviews.html"),
        _settings().adapters.metacritic,
        kind="critic",
        limit=50,
        max_chars=20,
    )
    assert len(batch.items) == 1
    assert len(batch.items[0].excerpt) == 20
    assert batch.truncated is True


def test_empty_reviews_page_is_empty_success() -> None:
    batch = parse_reviews(
        _html("empty_reviews.html"),
        _settings().adapters.metacritic,
        kind="critic",
        limit=50,
        max_chars=8000,
    )
    assert batch.items == []
    assert batch.truncated is False


def test_reviews_missing_markers_is_parse_error() -> None:
    try:
        parse_reviews(
            _html("empty_dom.html"),
            _settings().adapters.metacritic,
            kind="critic",
            limit=50,
            max_chars=8000,
        )
    except MetacriticAdapterError as exc:
        assert exc.code == "parse_error"
    else:
        raise AssertionError("expected parse_error")


def test_listing_limit() -> None:
    listing = parse_listing(
        _html("new_releases.html"),
        _settings().adapters.metacritic,
        source="new_releases",
        limit=1,
    )
    assert len(listing.items) == 1
    assert listing.items[0].position == 0


def test_odyssey_new_releases_listing() -> None:
    html = """
    <html><body>
      <section data-testid="new-game-release-carousel">
        <h2>New Releases</h2>
        <div data-testid="product-card">
          <a href="/game/valheim/" data-testid="product-card-content">
            <span data-testid="product-card-title">Valheim</span>
          </a>
        </div>
        <div data-testid="product-card">
          <a href="/game/halloween-the-game/">
            <h3 data-testid="product-card-title">Halloween: The Game</h3>
          </a>
        </div>
      </section>
    </body></html>
    """
    listing = parse_listing(html, _settings().adapters.metacritic, source="new_releases", limit=20)
    assert [item.slug for item in listing.items] == ["valheim", "halloween-the-game"]


def test_odyssey_browse_listing() -> None:
    html = """
    <html><body>
      <h1>All New Games by Release Date</h1>
      <button data-testid="dropdown-sort">Newest Releases</button>
      <div data-testid="filter-results">
        <div class="c-finderProductCard">
          <a href="/game/backseat/"><h3 data-testid="product-title">Backseat</h3></a>
        </div>
        <div class="c-finderProductCard">
          <a href="/game/witches/">
            <h3 data-testid="product-title">Elemental Witches</h3>
          </a>
        </div>
      </div>
    </body></html>
    """
    listing = parse_listing(
        html, _settings().adapters.metacritic, source="browse", page=1, limit=20
    )
    assert [item.slug for item in listing.items] == ["backseat", "witches"]
    full = parse_listing(html, _settings().adapters.metacritic, source="browse", page=1, limit=48)
    assert [item.slug for item in full.items] == ["backseat", "witches"]


def test_odyssey_card_json_ld_and_platforms() -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@type":"VideoGame","name":"Elden Ring",
       "description":"A New World Created By Hidetaka Miyazaki.",
       "datePublished":"2022-02-25","genre":"Action RPG",
       "image":"https://www.metacritic.com/a/img/elden.jpg",
       "publisher":[{"@type":"Organization","name":"Bandai Namco Games"},
                    {"@type":"Organization","name":"From Software"}],
       "trailer":{"embedUrl":"https://cdn.jwplayer.com/players/OXExoEAD.html"}}
      </script>
      <div data-testid="product-hero">
        <h1 data-testid="hero-title">Elden Ring</h1>
        <img alt="Elden Ring" src="https://cdn.jwplayer.com/poster.jpg"/>
        <div data-testid="hero-summary">Summary noisy Read More</div>
        <div data-testid="hero-summary-developer">
          <a href="/company/from-software/">From Software</a>
        </div>
        <div data-testid="featured-trailer"></div>
      </div>
      <a data-testid="product-score-card" href="/game/elden-ring/critic-reviews/?platform=pc">
        <span title="PC"></span>
        <div class="c-siteReviewScore"><span>94</span></div>
      </a>
      <a data-testid="product-score-card"
         href="/game/elden-ring/critic-reviews/?platform=playstation-5">
        <span title="PlayStation 5"></span>
        <div class="c-siteReviewScore" title="Metascore 96 out of 100"><span>96</span></div>
      </a>
    </body></html>
    """
    details = parse_game(html, _settings().adapters.metacritic, "elden-ring")
    assert details.title == "Elden Ring"
    assert details.developer == "From Software"
    assert details.publisher == "Bandai Namco Games"
    assert details.description is not None
    assert "Miyazaki" in details.description
    assert "Read More" not in details.description
    assert details.cover_source_url is not None
    assert "elden.jpg" in str(details.cover_source_url)
    assert "jwplayer.com" not in str(details.cover_source_url)
    assert details.video_url is not None
    assert "jwplayer.com" in str(details.video_url)
    assert details.release_date is not None
    assert details.release_date.isoformat() == "2022-02-25"
    by_code = {row.platform_code: row for row in details.platforms}
    assert by_code["pc"].metascore == 94
    assert by_code["ps5"].metascore == 96


def test_odyssey_span_developer_and_hero_userscore() -> None:
    html = """
    <html><body>
      <div data-testid="product-hero">
        <div data-testid="hero-title"><h1 class="hero-title__text">Valheim</h1></div>
        <div data-testid="hero-summary-developer">
          <p><span>Developer:</span><span>Iron Gate AB</span></p>
        </div>
        <div data-testid="platform-selector">
          <span title="PC"></span>
        </div>
        <div data-testid="product-score">
          <div data-testid="global-score-header">Metascore</div>
          <div data-testid="global-score-value-wrapper" aria-label="Metascore 90 out of 100">
            <span data-testid="global-score-value">90</span>
          </div>
        </div>
        <div data-testid="product-score">
          <div data-testid="global-score-header">User score</div>
          <div data-testid="global-score-value-wrapper"
               aria-label="User score 8.2 out of 10"
               title="User score 8.2 out of 10">
            <span data-testid="global-score-value">8.2</span>
          </div>
        </div>
      </div>
      <a data-testid="product-score-card" href="/game/valheim/critic-reviews/?platform=pc">
        <span title="PC"></span>
        <div class="c-siteReviewScore" aria-label="Metascore 90 out of 100"><span>90</span></div>
      </a>
      <div data-testid="product-score-card"
           to="/game/valheim/critic-reviews/?platform=xbox-series-x">
        <span title="Xbox Series X"></span>
        <div class="c-siteReviewScore" aria-label="Metascore tbd"><span>tbd</span></div>
      </div>
    </body></html>
    """
    details = parse_game(html, _settings().adapters.metacritic, "valheim")
    assert details.title == "Valheim"
    assert details.developer == "Iron Gate AB"
    by_code = {row.platform_code: row for row in details.platforms}
    assert by_code["pc"].metascore == 90
    assert by_code["pc"].userscore == 8.2
    assert by_code["xsx"].userscore is None


def test_odyssey_user_score_tbd_stays_empty() -> None:
    html = """
    <html><body>
      <div data-testid="product-hero">
        <h1 data-testid="hero-title">Valheim</h1>
        <div data-testid="product-score">
          <div data-testid="global-score-header">User score</div>
          <div data-testid="global-score-value-wrapper"
               aria-label="User score TBD" title="User score TBD">
            <span data-testid="global-score-tbd">tbd</span>
          </div>
        </div>
      </div>
      <a data-testid="product-score-card" href="/game/valheim/critic-reviews/?platform=pc">
        <span title="PC"></span>
        <div class="c-siteReviewScore"><span>90</span></div>
      </a>
    </body></html>
    """
    details = parse_game(html, _settings().adapters.metacritic, "valheim")
    by_code = {row.platform_code: row for row in details.platforms}
    assert by_code["pc"].metascore == 90
    assert by_code["pc"].userscore is None


def test_normalize_platform_url_slugs() -> None:
    assert normalize_platform_code("playstation-5") == "ps5"
    assert normalize_platform_code("xbox-series-x") == "xsx"
    assert normalize_platform_code("nintendo-switch-2") == "ns2"
    assert normalize_platform_code("xbox-one") == "xboxone"


def test_odyssey_reviews() -> None:
    html = """
    <html><body>
      <section data-testid="critic-reviews">
        <article data-testid="review-card">
          <a data-testid="review-card-header" href="/publication/ign/">
            <div class="c-siteReviewScore"><span>95</span></div>
            IGN
          </a>
          <div data-testid="review-quote-text">Challenging combat and a vast world.</div>
        </article>
      </section>
    </body></html>
    """
    batch = parse_reviews(
        html, _settings().adapters.metacritic, kind="critic", limit=50, max_chars=8000
    )
    assert len(batch.items) == 1
    assert "combat" in batch.items[0].excerpt
    assert batch.items[0].score == 95


def test_odyssey_reviews_filters_without_legacy_section() -> None:
    html = """
    <html><body>
      <h1>PlayStation 5 Critic Reviews</h1>
      <div data-testid="reviews-filters"></div>
      <article data-testid="review-card">
        <a data-testid="review-card-header" href="/publication/ign/">IGN</a>
        <div class="c-siteReviewScore"><span>88</span></div>
        <div data-testid="review-quote-text">Solid combat.</div>
      </article>
    </body></html>
    """
    batch = parse_reviews(
        html, _settings().adapters.metacritic, kind="critic", limit=50, max_chars=8000
    )
    assert len(batch.items) == 1
    assert batch.items[0].excerpt == "Solid combat."
    assert batch.items[0].score == 88
