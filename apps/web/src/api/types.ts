import type { components, operations } from "./schema";

export type CollectionStateRead = components["schemas"]["CollectionStateRead"];
export type GameHydrationRead = components["schemas"]["GameHydrationRead"];
export type GameCard = components["schemas"]["GameCardRead"];
export type GameListItem = components["schemas"]["GameListItemRead"];
export type GameListResponse = components["schemas"]["GameListResponse"];
export type LetsPlayRead = components["schemas"]["LetsPlayRead"];
export type PlatformListResponse = components["schemas"]["PlatformListResponse"];
export type PlatformScore = components["schemas"]["PlatformScore"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
export type ReviewSummary = components["schemas"]["ReviewSummary"];
export type SimilarGameRef = components["schemas"]["SimilarGameRef"];
export type GameListQuery = NonNullable<
  operations["list_games_api_v1_games_get"]["parameters"]["query"]
>;
export type GameSort = NonNullable<GameListQuery["sort"]>;
export type SortOrder = NonNullable<GameListQuery["order"]>;
export type LetsPlayStatus = NonNullable<LetsPlayRead["status"]>;
export type MonitorSnapshot = components["schemas"]["MonitorSnapshot"];
export type WorkerHeartbeatRead = components["schemas"]["WorkerHeartbeatRead"];
export type MonitorRunRead = components["schemas"]["MonitorRunRead"];
export type MonitorItemRead = components["schemas"]["MonitorItemRead"];
export type MonitorScrapeRead = components["schemas"]["MonitorScrapeRead"];
export type RunAccepted = components["schemas"]["RunAcceptedResponse"];
