import { useQuery } from "@tanstack/react-query";

import { fetchGame, fetchGames, fetchPlatforms } from "./client";
import { hydrationIsLoading } from "../lib/collection";
import { queryKeys } from "./query-keys";
import type { GameListQuery } from "./types";

export function useGamesQuery(filters: GameListQuery) {
  return useQuery({
    queryKey: queryKeys.games(filters),
    queryFn: () => fetchGames(filters),
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => item.catalog_collection.status === "loading")
        ? 2500
        : false,
  });
}

export function useGameQuery(slug: string) {
  return useQuery({
    queryKey: queryKeys.game(slug),
    queryFn: () => fetchGame(slug),
    enabled: slug.length > 0,
    refetchInterval: (query) => (hydrationIsLoading(query.state.data?.hydration) ? 2500 : false),
  });
}

export function usePlatformsQuery() {
  return useQuery({
    queryKey: queryKeys.platforms(),
    queryFn: fetchPlatforms,
  });
}
