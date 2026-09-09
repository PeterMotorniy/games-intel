import { useQuery } from "@tanstack/react-query";

import { fetchGame, fetchGames, fetchPlatforms } from "./client";
import { queryKeys } from "./query-keys";
import type { GameListQuery } from "./types";

export function useGamesQuery(filters: GameListQuery) {
  return useQuery({
    queryKey: queryKeys.games(filters),
    queryFn: () => fetchGames(filters),
  });
}

export function useGameQuery(slug: string) {
  return useQuery({
    queryKey: queryKeys.game(slug),
    queryFn: () => fetchGame(slug),
    enabled: slug.length > 0,
  });
}

export function usePlatformsQuery() {
  return useQuery({
    queryKey: queryKeys.platforms(),
    queryFn: fetchPlatforms,
  });
}
