import { Link } from "react-router";

import type { GameListItem } from "../api/types";
import { displayTitle } from "../lib/format";
import { CoverImage } from "./CoverImage";
import { ScoreBadge } from "./ScoreBadge";

type GameCardProps = {
  game: GameListItem;
};

export function GameCard({ game }: GameCardProps) {
  const platforms = game.platforms ?? [];
  const title = displayTitle(game.title, game.metacritic_slug);
  return (
    <Link className="game-card-link" to={`/games/${game.metacritic_slug}`}>
      <article className="game-card">
        <CoverImage title={title} coverUrl={game.cover_url} className="game-card__cover" />
        <div className="game-card__body">
          <h2 className="game-card__title">{title}</h2>
          {game.developer?.trim() ? (
            <p className="meta-pill meta-pill--developer">{game.developer}</p>
          ) : null}
          <div className="game-card__scores">
            <ScoreBadge value={game.metascore} kind="meta" label="Metascore" />
            <ScoreBadge value={game.userscore} kind="user" label="Userscore" />
          </div>
          {platforms.length > 0 ? (
            <ul className="chips" aria-label="Platforms">
              {platforms.map((code) => (
                <li key={code} className="chip chip--platform">
                  {code}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </article>
    </Link>
  );
}
