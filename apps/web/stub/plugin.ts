import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

import type { components } from "../src/api/schema";
import { STUB_GAMES, STUB_LIST, STUB_PLATFORMS } from "./catalog";
import { acceptManualRun, getMonitorSnapshot, writeSseSnapshot } from "./monitor";

type GameSort = components["schemas"]["PaginationMeta"]["sort"];
type SortOrder = components["schemas"]["PaginationMeta"]["order"];

const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

function problem(res: ServerResponse, status: number, title: string, detail: string): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/problem+json");
  res.end(JSON.stringify({ type: "about:blank", title, status, detail }));
}

function compareNullable(
  left: number | null | undefined,
  right: number | null | undefined,
  order: SortOrder,
): number {
  if (left == null && right == null) {
    return 0;
  }
  if (left == null) {
    return 1;
  }
  if (right == null) {
    return -1;
  }
  return order === "asc" ? left - right : right - left;
}

function listGames(url: URL): components["schemas"]["GameListResponse"] {
  const q = (url.searchParams.get("q") ?? "").trim().toLowerCase();
  const platform = url.searchParams.get("platform")?.trim() || "";
  const sort = (url.searchParams.get("sort") as GameSort | null) ?? "metascore";
  const order = (url.searchParams.get("order") as SortOrder | null) ?? "desc";
  const page = Math.max(1, Number(url.searchParams.get("page") ?? "1") || 1);
  const pageSize = Math.max(1, Number(url.searchParams.get("page_size") ?? "20") || 20);

  let items = STUB_LIST.map((item) => ({ ...item }));
  if (q) {
    items = items.filter((item) => item.title.toLowerCase().includes(q));
  }
  if (platform) {
    items = items.filter((item) => (item.platforms ?? []).includes(platform));
  }
  items.sort((a, b) => {
    if (sort === "title") {
      const cmp = a.title.localeCompare(b.title);
      return order === "asc" ? cmp : -cmp;
    }
    if (sort === "updated") {
      const cmp = a.updated_at.localeCompare(b.updated_at);
      return order === "asc" ? cmp : -cmp;
    }
    if (sort === "userscore") {
      return compareNullable(a.userscore, b.userscore, order);
    }
    return compareNullable(a.metascore, b.metascore, order);
  });
  const total = items.length;
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    meta: { page, page_size: pageSize, total, sort, order },
  };
}

function handle(req: IncomingMessage, res: ServerResponse): boolean {
  if (!req.url) {
    return false;
  }
  const url = new URL(req.url, "http://vite.local");
  if (req.method === "POST" && url.pathname === "/api/v1/runs") {
    sendJson(res, 202, acceptManualRun());
    return true;
  }
  if (req.method !== "GET") {
    return false;
  }
  if (url.pathname === "/api/v1/monitor") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    res.end(JSON.stringify(getMonitorSnapshot()));
    return true;
  }
  if (url.pathname === "/api/v1/monitor/stream") {
    writeSseSnapshot(req, res);
    return true;
  }
  if (url.pathname === "/api/v1/games") {
    sendJson(res, 200, listGames(url));
    return true;
  }
  const gameMatch = /^\/api\/v1\/games\/([^/]+)$/.exec(url.pathname);
  if (gameMatch) {
    const slug = decodeURIComponent(gameMatch[1] ?? "");
    const card = STUB_GAMES[slug];
    if (!card) {
      problem(res, 404, "Not Found", `Game '${slug}' was not found`);
      return true;
    }
    sendJson(res, 200, {
      ...card,
      similar: (card.similar ?? []).filter((item) => item.metacritic_slug !== slug),
    });
    return true;
  }
  if (url.pathname === "/api/v1/platforms") {
    sendJson(res, 200, { items: [...STUB_PLATFORMS] });
    return true;
  }
  const coverMatch = /^\/api\/v1\/media\/covers\/([^/]+)$/.exec(url.pathname);
  if (coverMatch) {
    const slug = decodeURIComponent(coverMatch[1] ?? "");
    if (!STUB_GAMES[slug]) {
      problem(res, 404, "Not Found", "Cover file is missing");
      return true;
    }
    res.statusCode = 200;
    res.setHeader("Content-Type", "image/png");
    res.setHeader("Cache-Control", "public, max-age=86400");
    res.end(PNG_1X1);
    return true;
  }
  return false;
}

export function catalogStubPlugin(enabled: boolean): Plugin {
  return {
    name: "catalog-stub",
    configureServer(server) {
      if (!enabled) {
        return;
      }
      server.middlewares.use((req, res, next) => {
        if (handle(req, res)) {
          return;
        }
        next();
      });
    },
  };
}
