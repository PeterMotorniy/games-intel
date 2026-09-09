export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "not started";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(parsed);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

export function formatTaskTiming(
  status: "requested" | "pending" | "running" | "completed" | "failed" | "degraded",
  startedAt: string | null | undefined,
  endedAt: string | null | undefined,
  nowMs: number,
): string {
  if (!startedAt) {
    return "Not started";
  }
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) {
    return "Not started";
  }
  if (endedAt) {
    const end = new Date(endedAt).getTime();
    const elapsed = Number.isNaN(end) ? nowMs - start : end - start;
    return `Finished in ${formatDuration(elapsed)}`;
  }
  if (status === "pending" || status === "requested") {
    return "Not started";
  }
  if (status === "completed" || status === "failed" || status === "degraded") {
    return "Finished";
  }
  return `Active ${formatDuration(nowMs - start)}`;
}

export function displayTitle(title: string | null | undefined, slug: string): string {
  const trimmed = title?.trim() ?? "";
  if (trimmed) {
    return trimmed;
  }
  const fromSlug = slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
  return fromSlug || slug;
}

export function metacriticGameUrl(slug: string, listingUrl?: string | null): string {
  if (listingUrl?.trim()) {
    return listingUrl.trim();
  }
  return `https://www.metacritic.com/game/${slug}/`;
}

export function formatReleaseDate(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

export function formatUserscore(value: number | null | undefined): string {
  if (value == null) {
    return "n/a";
  }
  return value.toFixed(1);
}

export function scoreTone(value: number | null | undefined, kind: "meta" | "user"): "high" | "mid" | "low" | "empty" {
  if (value == null) {
    return "empty";
  }
  if (kind === "user") {
    if (value >= 7.5) {
      return "high";
    }
    if (value >= 5) {
      return "mid";
    }
    return "low";
  }
  if (value >= 75) {
    return "high";
  }
  if (value >= 50) {
    return "mid";
  }
  return "low";
}
