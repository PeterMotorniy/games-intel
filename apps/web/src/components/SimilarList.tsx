import { Link } from "react-router";

import type { SimilarGameRef } from "../api/types";
import { displayTitle } from "../lib/format";

type SimilarListProps = {
  currentSlug: string;
  items: SimilarGameRef[] | undefined;
};

export function SimilarList({ currentSlug, items }: SimilarListProps) {
  const neighbors = (items ?? []).filter((item) => item.metacritic_slug !== currentSlug);
  if (neighbors.length === 0) {
    return <p className="muted">Similar games will appear after scoring.</p>;
  }
  return (
    <ul className="similar-list">
      {neighbors.map((item) => (
        <li key={item.metacritic_slug}>
          <Link className="similar-list__link" to={`/games/${item.metacritic_slug}`}>
            {displayTitle(item.title, item.metacritic_slug)}
          </Link>
        </li>
      ))}
    </ul>
  );
}
