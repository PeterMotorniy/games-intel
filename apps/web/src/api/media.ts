import { apiBaseUrl } from "./config";

const LOCAL_COVER = /^\/api\/v1\/media\/covers\/[A-Za-z0-9_-]+$/;

export function resolveMediaUrl(coverUrl: string | null | undefined): string | undefined {
  if (!coverUrl) {
    return undefined;
  }
  const path = coverUrl.trim();
  if (!LOCAL_COVER.test(path)) {
    return undefined;
  }
  if (apiBaseUrl.startsWith("/")) {
    return path;
  }
  return new URL(path, apiBaseUrl).href;
}
