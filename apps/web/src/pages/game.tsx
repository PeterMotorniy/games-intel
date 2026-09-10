import { Link, useParams } from "react-router";

import { ApiError } from "../api/client";
import { useGameQuery } from "../api/queries";
import { CollectionSlot } from "../components/CollectionNotice";
import { CoverImage } from "../components/CoverImage";
import { LetsPlayBlock } from "../components/LetsPlayBlock";
import { MetacriticLink } from "../components/MetacriticLink";
import { PageState } from "../components/PageState";
import { ReviewBlock } from "../components/ReviewBlock";
import { ScoreBadge } from "../components/ScoreBadge";
import { SimilarList } from "../components/SimilarList";
import { displayTitle, formatReleaseDate } from "../lib/format";

export function GamePage() {
  const { slug = "" } = useParams();
  const query = useGameQuery(slug);

  if (query.isPending) {
    return (
      <div className="page">
        <PageState kind="loading" title="Loading game..." />
        <div className="skeleton-card skeleton-card--wide" aria-hidden="true">
          <div className="skeleton skeleton--cover" />
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line skeleton--short" />
        </div>
      </div>
    );
  }

  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404;
    return (
      <div className="page">
        <p>
          <Link to="/">Back to catalog</Link>
        </p>
        <PageState
          kind="error"
          title={notFound ? "Game not found" : "Could not load the game"}
          detail={query.error instanceof Error ? query.error.message : null}
          onRetry={notFound ? undefined : () => void query.refetch()}
        />
      </div>
    );
  }

  const game = query.data;
  const hydration = game.hydration;
  const catalog = hydration.catalog;
  const platforms = game.platforms ?? [];
  const genres = game.genres ?? [];
  const release = formatReleaseDate(game.release_date);
  const title = displayTitle(game.title, game.metacritic_slug);
  const developer = game.developer?.trim() || null;
  const publisher = game.publisher?.trim() || null;

  return (
    <article className="page game-page">
      <p>
        <Link to="/">Back to catalog</Link>
      </p>
      <header className="game-hero">
        <CoverImage
          title={title}
          coverUrl={game.cover_url}
          collection={catalog}
          className="game-hero__cover"
        />
        <div className="game-hero__meta">
          <div className="game-hero__heading">
            <h1>{title}</h1>
            <div className="game-hero__scores" aria-label="Overall scores">
              <ScoreBadge
                value={game.metascore}
                kind="meta"
                label="Overall Metascore"
                collection={catalog}
                size="hero"
              />
              <ScoreBadge
                value={game.userscore}
                kind="user"
                label="Overall Userscore"
                collection={catalog}
                size="hero"
              />
            </div>
          </div>
          <div className="game-hero__pills">
            <MetacriticLink slug={game.metacritic_slug} />
          </div>
          <dl className="game-facts">
            <div className="game-fact">
              <dt>Developer</dt>
              <dd>
                <CollectionSlot
                  collection={catalog}
                  hasValue={Boolean(developer)}
                  topic="Developer"
                  layout="compact"
                  emptyTitle="No developer on Metacritic"
                >
                  <p className="meta-pill meta-pill--developer">{developer}</p>
                </CollectionSlot>
              </dd>
            </div>
            <div className="game-fact">
              <dt>Publisher</dt>
              <dd>
                <CollectionSlot
                  collection={catalog}
                  hasValue={Boolean(publisher)}
                  topic="Publisher"
                  layout="compact"
                  emptyTitle="No publisher on Metacritic"
                >
                  <p className="meta-pill meta-pill--publisher">{publisher}</p>
                </CollectionSlot>
              </dd>
            </div>
            <div className="game-fact">
              <dt>Released</dt>
              <dd>
                <CollectionSlot
                  collection={catalog}
                  hasValue={Boolean(release)}
                  topic="Release date"
                  layout="compact"
                  emptyTitle="No release date on Metacritic"
                >
                  <p>{release}</p>
                </CollectionSlot>
              </dd>
            </div>
          </dl>
          <CollectionSlot
            collection={catalog}
            hasValue={genres.length > 0}
            topic="Genres"
            layout="compact"
            emptyTitle="No genres on Metacritic"
          >
            <ul className="chips" aria-label="Genres">
              {genres.map((genre) => (
                <li key={genre} className="chip chip--genre">
                  {genre}
                </li>
              ))}
            </ul>
          </CollectionSlot>
        </div>
      </header>

      <section className="panel" aria-labelledby="platforms-heading">
        <h2 id="platforms-heading">Platforms and scores</h2>
        <CollectionSlot
          collection={catalog}
          hasValue={platforms.length > 0}
          topic="Platforms and scores"
          emptyTitle="No platforms or scores on Metacritic"
        >
          <ul className="platform-scores">
            {platforms.map((row) => (
              <li key={row.platform_code} className="platform-scores__row">
                <span className="chip chip--platform">{row.platform_code}</span>
                <ScoreBadge
                  value={row.metascore}
                  kind="meta"
                  label="Metascore"
                  collection={catalog}
                />
                <ScoreBadge
                  value={row.userscore}
                  kind="user"
                  label="Userscore"
                  collection={catalog}
                />
              </li>
            ))}
          </ul>
        </CollectionSlot>
      </section>

      <section className="panel" aria-labelledby="description-heading">
        <h2 id="description-heading">Description</h2>
        <CollectionSlot
          collection={catalog}
          hasValue={Boolean(game.description?.trim())}
          topic="Description"
          emptyTitle="No description on Metacritic"
        >
          <p>{game.description}</p>
        </CollectionSlot>
      </section>

      <section className="panel" aria-labelledby="video-heading">
        <h2 id="video-heading">Video</h2>
        <CollectionSlot
          collection={catalog}
          hasValue={Boolean(game.video_url)}
          topic="Video"
          emptyTitle="No trailer on Metacritic"
        >
          <p>
            <a href={game.video_url ?? undefined} rel="noreferrer" target="_blank">
              Watch trailer
            </a>
          </p>
        </CollectionSlot>
      </section>

      <ReviewBlock
        heading="Critic reviews"
        headingId="critic-reviews"
        topic="Critic reviews"
        summary={game.critic}
        collection={hydration.critic}
      />
      <ReviewBlock
        heading="Player reviews"
        headingId="user-reviews"
        topic="Player reviews"
        summary={game.user}
        collection={hydration.user}
      />
      <LetsPlayBlock letsplay={game.letsplay} collection={hydration.letsplay} />

      <section className="panel" aria-labelledby="similar-heading">
        <h2 id="similar-heading">Similar games</h2>
        <SimilarList
          currentSlug={game.metacritic_slug}
          items={game.similar}
          collection={hydration.similar}
        />
      </section>
    </article>
  );
}
