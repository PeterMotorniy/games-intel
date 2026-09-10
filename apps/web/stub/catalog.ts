import type { components } from "../src/api/schema";
import { READY_COLLECTION, READY_HYDRATION } from "../src/lib/collection";

export type GameListItem = components["schemas"]["GameListItemRead"];
export type GameCard = components["schemas"]["GameCardRead"];

export const STUB_PLATFORMS = ["ns2", "pc", "ps5", "xbox-series-x"] as const;

const ELDEN: GameCard = {
  metacritic_slug: "elden-ring",
  title: "Elden Ring",
  cover_url: "/api/v1/media/covers/elden-ring",
  developer: "FromSoftware",
  publisher: "Bandai Namco",
  description: "An open-world action RPG set in the Lands Between.",
  video_url: "https://www.youtube.com/watch?v=E3Huy2cdih0",
  genres: ["Action", "RPG"],
  release_date: "2022-02-25",
  metascore: 96,
  userscore: 7.8,
  platforms: [
    { platform_code: "ps5", metascore: 96, userscore: 7.8 },
    { platform_code: "pc", metascore: 94, userscore: 7.2 },
  ],
  critic: {
    likes: ["exploration", "combat"],
    dislikes: ["performance on launch"],
    summary: "Vast world with exceptional boss design.",
  },
  user: {
    likes: ["freedom", "atmosphere"],
    dislikes: ["difficulty spikes"],
    summary: "Harsh but fair, endlessly replayable.",
  },
  letsplay: {
    status: "ok",
    video_url: "https://www.youtube.com/watch?v=letsplay-elden",
    video_title: "Elden Ring Let's Play Episode 1",
    view_count: 2_400_000,
    conclusion: "Блогер подчёркивает свободу исследования и зрелищность боссов.",
    highlights: ["open world", "boss fights"],
  },
  similar: [
    { metacritic_slug: "sekiro", title: "Sekiro: Shadows Die Twice", score: 0.87, rank: 1 },
    { metacritic_slug: "silksong", title: "Hollow Knight: Silksong", score: 0.61, rank: 2 },
  ],
  hydration: READY_HYDRATION,
};

const SEKIRO: GameCard = {
  metacritic_slug: "sekiro",
  title: "Sekiro: Shadows Die Twice",
  cover_url: "/api/v1/media/covers/sekiro",
  developer: "FromSoftware",
  publisher: "Activision",
  description: "A shinobi action game focused on posture and precision.",
  video_url: "https://www.youtube.com/watch?v=rXMX4YJ7Lks",
  genres: ["Action", "Adventure"],
  release_date: "2019-03-22",
  metascore: 90,
  userscore: 8.4,
  platforms: [
    { platform_code: "ps5", metascore: 90, userscore: 8.4 },
    { platform_code: "pc", metascore: 88, userscore: 8.1 },
  ],
  critic: {
    likes: ["combat", "bosses"],
    dislikes: ["steep learning curve"],
    summary: "One of the best action combat systems in years.",
  },
  user: {
    likes: ["deflection", "setting"],
    dislikes: ["checkpoint placement"],
    summary: "Demanding and immensely satisfying.",
  },
  letsplay: {
    status: "ok",
    video_url: "https://www.youtube.com/watch?v=letsplay-sekiro",
    video_title: "Sekiro Let's Play",
    view_count: 980_000,
    conclusion: "Рассказчик отмечает ритм боя и чувство прогресса после обучения.",
    highlights: ["deflection"],
  },
  similar: [{ metacritic_slug: "elden-ring", title: "Elden Ring", score: 0.87, rank: 1 }],
  hydration: READY_HYDRATION,
};

const SILKSONG: GameCard = {
  metacritic_slug: "silksong",
  title: "Hollow Knight: Silksong",
  cover_url: "/api/v1/media/covers/silksong",
  developer: "Team Cherry",
  publisher: "Team Cherry",
  description: "Hornet's journey through a new kingdom.",
  video_url: null,
  genres: ["Action", "Platformer"],
  release_date: "2025-09-04",
  metascore: 91,
  userscore: 8.6,
  platforms: [
    { platform_code: "ns2", metascore: 91, userscore: 8.6 },
    { platform_code: "pc", metascore: 90, userscore: 8.4 },
  ],
  critic: {
    likes: ["movement", "art"],
    dislikes: ["difficulty"],
    summary: "A precise and beautiful Metroidvania.",
  },
  user: {
    likes: ["exploration"],
    dislikes: ["runbacks"],
    summary: "Worth the wait for most players.",
  },
  letsplay: {
    status: "transcript_unavailable",
    video_url: "https://www.youtube.com/watch?v=letsplay-silksong",
    video_title: "Silksong Let's Play",
    view_count: 410_000,
    conclusion: null,
    highlights: null,
  },
  similar: [{ metacritic_slug: "elden-ring", title: "Elden Ring", score: 0.61, rank: 1 }],
  hydration: { ...READY_HYDRATION, letsplay: { status: "empty", error_type: null, error_message: null } },
};

const EXPEDITION: GameCard = {
  metacritic_slug: "clair-obscur-expedition-33",
  title: "Clair Obscur: Expedition 33",
  cover_url: "/api/v1/media/covers/clair-obscur-expedition-33",
  developer: "Sandfall Interactive",
  publisher: "Kepler Interactive",
  description: "A turn-based RPG with real-time parries.",
  video_url: "https://www.youtube.com/watch?v=expedition-trailer",
  genres: ["RPG"],
  release_date: "2025-04-24",
  metascore: 92,
  userscore: 8.8,
  platforms: [
    { platform_code: "ps5", metascore: 92, userscore: 8.8 },
    { platform_code: "xbox-series-x", metascore: 91, userscore: 8.7 },
    { platform_code: "pc", metascore: 91, userscore: 8.6 },
  ],
  critic: {
    likes: ["story", "art direction"],
    dislikes: ["some grinding"],
    summary: "A confident debut with striking presentation.",
  },
  user: {
    likes: ["characters", "music"],
    dislikes: ["performance on PC"],
    summary: "Emotional and stylish.",
  },
  letsplay: {
    status: "quota_exceeded",
    video_url: null,
    video_title: null,
    view_count: null,
    conclusion: null,
    highlights: null,
  },
  similar: [{ metacritic_slug: "elden-ring", title: "Elden Ring", score: 0.44, rank: 1 }],
  hydration: { ...READY_HYDRATION, letsplay: { status: "error", error_type: null, error_message: null } },
};

const ANIMAL: GameCard = {
  metacritic_slug: "animal-well",
  title: "Animal Well",
  cover_url: "/api/v1/media/covers/animal-well",
  developer: "Shared Memory",
  publisher: "Bigmode",
  description: "A mysterious pixel-art exploration game.",
  video_url: "https://www.youtube.com/watch?v=animal-well-trailer",
  genres: ["Adventure", "Puzzle"],
  release_date: "2024-05-09",
  metascore: 91,
  userscore: 8.2,
  platforms: [
    { platform_code: "pc", metascore: 91, userscore: 8.2 },
    { platform_code: "ns2", metascore: 90, userscore: 8.0 },
  ],
  critic: null,
  user: null,
  letsplay: {
    status: "no_video",
    video_url: null,
    video_title: null,
    view_count: null,
    conclusion: null,
    highlights: null,
  },
  similar: [],
  hydration: {
    catalog: READY_COLLECTION,
    critic: { status: "idle", error_type: null, error_message: null },
    user: { status: "idle", error_type: null, error_message: null },
    letsplay: { status: "empty", error_type: null, error_message: null },
    similar: { status: "empty", error_type: null, error_message: null },
  },
};

export const STUB_GAMES: Record<string, GameCard> = {
  [ELDEN.metacritic_slug]: ELDEN,
  [SEKIRO.metacritic_slug]: SEKIRO,
  [SILKSONG.metacritic_slug]: SILKSONG,
  [EXPEDITION.metacritic_slug]: EXPEDITION,
  [ANIMAL.metacritic_slug]: ANIMAL,
};

const UPDATED: Record<string, string> = {
  "elden-ring": "2026-09-08T10:00:00Z",
  sekiro: "2026-09-08T09:00:00Z",
  silksong: "2026-09-07T18:00:00Z",
  "clair-obscur-expedition-33": "2026-09-07T12:00:00Z",
  "animal-well": "2026-09-06T08:00:00Z",
};

export function toListItem(card: GameCard): GameListItem {
  const platforms = card.platforms ?? [];
  const metas = platforms.map((row) => row.metascore).filter((value): value is number => value != null);
  const users = platforms.map((row) => row.userscore).filter((value): value is number => value != null);
  return {
    metacritic_slug: card.metacritic_slug,
    title: card.title,
    cover_url: card.cover_url,
    developer: card.developer,
    metascore: metas.length > 0 ? Math.max(...metas) : null,
    userscore: users.length > 0 ? Math.max(...users) : null,
    platforms: platforms.map((row) => row.platform_code),
    updated_at: UPDATED[card.metacritic_slug] ?? "2026-09-08T00:00:00Z",
    catalog_collection: card.hydration.catalog,
  };
}

export const STUB_LIST: GameListItem[] = Object.values(STUB_GAMES).map(toListItem);
