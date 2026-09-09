import { Link } from "react-router";

import type { CollectionStateRead, SimilarGameRef } from "../api/types";
import { displayTitle } from "../lib/format";
import { CollectionSlot } from "./CollectionNotice";

type SimilarListProps = {
  currentSlug: string;
  items: SimilarGameRef[] | undefined;
  collection: CollectionStateRead | null | undefined;
};

export function SimilarList({ currentSlug, items, collection }: SimilarListProps) {
  const neighbors = (items ?? []).filter((item) => item.metacritic_slug !== currentSlug);
  return (
    <CollectionSlot
      collection={collection}
      hasValue={neighbors.length > 0}
      topic="Similar games"
      emptyTitle="No similar games in the catalog yet"
      idleTitle="Similar games have not been scored yet"
      loadingTitle="Finding similar games"
      errorTitle="Could not score similar games"
    >
      <ul className="similar-list">
        {neighbors.map((item) => (
          <li key={item.metacritic_slug}>
            <Link className="similar-list__link" to={`/games/${item.metacritic_slug}`}>
              {displayTitle(item.title, item.metacritic_slug)}
            </Link>
          </li>
        ))}
      </ul>
    </CollectionSlot>
  );
}
