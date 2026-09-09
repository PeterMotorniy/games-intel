import type { CollectionStateRead, GameHydrationRead } from "../api/types";

export type CollectionKind = CollectionStateRead["status"];

export const READY_COLLECTION: CollectionStateRead = {
  status: "ready",
  error_type: null,
  error_message: null,
};

export const READY_HYDRATION: GameHydrationRead = {
  catalog: READY_COLLECTION,
  critic: READY_COLLECTION,
  user: READY_COLLECTION,
  letsplay: READY_COLLECTION,
  similar: READY_COLLECTION,
};

export function fieldState(
  hasValue: boolean,
  collection: CollectionStateRead | null | undefined,
): CollectionKind {
  if (hasValue) {
    return "ready";
  }
  const status = collection?.status ?? "idle";
  if (status === "ready") {
    return "empty";
  }
  return status;
}

export function hydrationIsLoading(hydration: GameHydrationRead | undefined): boolean {
  if (!hydration) {
    return false;
  }
  return Object.values(hydration).some((row) => row.status === "loading");
}

export function collectionTitle(
  kind: Exclude<CollectionKind, "ready">,
  topic: string,
): string {
  if (kind === "idle") {
    return `${topic} not collected yet`;
  }
  if (kind === "loading") {
    return `Collecting ${topic.toLowerCase()}`;
  }
  if (kind === "empty") {
    return `No ${topic.toLowerCase()} found`;
  }
  return `Could not collect ${topic.toLowerCase()}`;
}
