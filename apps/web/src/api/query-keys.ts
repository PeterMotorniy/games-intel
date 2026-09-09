import type { GameListQuery } from "./types";

export const queryKeys = {
  platforms: () => ["platforms"] as const,
  games: (filters: GameListQuery) => ["games", filters] as const,
  game: (slug: string) => ["game", slug] as const,
  monitor: () => ["monitor"] as const,
};
