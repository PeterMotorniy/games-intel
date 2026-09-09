import { Link, useParams } from "react-router";

import { ApiError } from "../api/client";
import { useGameQuery } from "../api/queries";
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
        <CoverImage title={title} coverUrl={game.cover_url} className="game-hero__cover" />
        <div className="game-hero__meta">
          <h1>{title}</h1>
          <div className="game-hero__pills">
            {developer ? <p className="meta-pill meta-pill--developer">{developer}</p> : null}
            {publisher ? <p className="meta-pill meta-pill--publisher">{publisher}</p> : null}
            <MetacriticLink slug={game.metacritic_slug} />
          </div>
          {release ? (
            <p>
              <span className="meta-label">Released</span> {release}
            </p>
          ) : null}
          {genres.length > 0 ? (
            <ul className="chips" aria-label="Genres">
              {genres.map((genre) => (
                <li key={genre} className="chip chip--genre">
                  {genre}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </header>

      {platforms.length > 0 ? (
        <section className="panel" aria-labelledby="platforms-heading">
          <h2 id="platforms-heading">Platforms and scores</h2>
          <ul className="platform-scores">
            {platforms.map((row) => (
              <li key={row.platform_code} className="platform-scores__row">
                <span className="chip chip--platform">{row.platform_code}</span>
                <ScoreBadge value={row.metascore} kind="meta" label="Metascore" />
                <ScoreBadge value={row.userscore} kind="user" label="Userscore" />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {game.description ? (
        <section className="panel" aria-labelledby="description-heading">
          <h2 id="description-heading">Description</h2>
          <p>{game.description}</p>
        </section>
      ) : null}

      {game.video_url ? (
        <section className="panel" aria-labelledby="video-heading">
          <h2 id="video-heading">Video</h2>
          <p>
            <a href={game.video_url} rel="noreferrer" target="_blank">
              Watch trailer
            </a>
          </p>
        </section>
      ) : null}

      <ReviewBlock heading="Critic reviews" headingId="critic-reviews" summary={game.critic} />
      <ReviewBlock heading="Player reviews" headingId="user-reviews" summary={game.user} />
      <LetsPlayBlock letsplay={game.letsplay} />

      <section className="panel" aria-labelledby="similar-heading">
        <h2 id="similar-heading">Similar games</h2>
        <SimilarList currentSlug={game.metacritic_slug} items={game.similar} />
      </section>
    </article>
  );
}
