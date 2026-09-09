import { apiBaseUrl } from "./config";
import type {
  GameCard,
  GameListQuery,
  GameListResponse,
  MonitorSnapshot,
  PlatformListResponse,
  ProblemDetails,
  RunAccepted,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string | null;

  constructor(status: number, title: string, detail: string | null) {
    super(detail || title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.detail = detail;
  }
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return typeof record.title === "string" && typeof record.status === "number";
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (isProblemDetails(body)) {
      return new ApiError(body.status, body.title, body.detail ?? null);
    }
  } catch {
    // Fall through to status text when the body is not problem+json.
  }
  return new ApiError(response.status, response.statusText || "HTTP Error", null);
}

function buildUrl(path: string, query?: GameListQuery): string {
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function getJson<T>(path: string, query?: GameListQuery, cache: RequestCache = "default"): Promise<T> {
  const response = await fetch(buildUrl(path, query), { cache });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function fetchGames(filters: GameListQuery): Promise<GameListResponse> {
  return getJson<GameListResponse>("/games", filters);
}

export function fetchGame(slug: string): Promise<GameCard> {
  return getJson<GameCard>(`/games/${encodeURIComponent(slug)}`);
}

export function fetchPlatforms(): Promise<PlatformListResponse> {
  return getJson<PlatformListResponse>("/platforms");
}

export function fetchMonitor(): Promise<MonitorSnapshot> {
  return getJson<MonitorSnapshot>("/monitor", undefined, "no-store");
}

export function monitorStreamUrl(): string {
  return buildUrl("/monitor/stream");
}

export async function startRun(): Promise<RunAccepted> {
  const response = await fetch(buildUrl("/runs"), { method: "POST" });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as RunAccepted;
}
