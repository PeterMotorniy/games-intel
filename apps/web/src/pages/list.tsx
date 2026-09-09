import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useGamesQuery, usePlatformsQuery } from "../api/queries";
import type { GameListQuery, GameSort, SortOrder } from "../api/types";
import { GameCard } from "../components/GameCard";
import { PageState, SkeletonGrid } from "../components/PageState";
import { PlatformFilter } from "../components/PlatformFilter";

const SORT_OPTIONS: { value: string; label: string; sort: GameSort; order: SortOrder }[] = [
  { value: "metascore:desc", label: "Metascore, high to low", sort: "metascore", order: "desc" },
  { value: "metascore:asc", label: "Metascore, low to high", sort: "metascore", order: "asc" },
  { value: "userscore:desc", label: "Userscore, high to low", sort: "userscore", order: "desc" },
  { value: "userscore:asc", label: "Userscore, low to high", sort: "userscore", order: "asc" },
  { value: "title:asc", label: "Title, A to Z", sort: "title", order: "asc" },
  { value: "title:desc", label: "Title, Z to A", sort: "title", order: "desc" },
  { value: "updated:desc", label: "Recently updated", sort: "updated", order: "desc" },
];

const SEARCH_DEBOUNCE_MS = 300;

function isSort(value: string | null): value is GameSort {
  return value === "metascore" || value === "userscore" || value === "title" || value === "updated";
}

function isOrder(value: string | null): value is SortOrder {
  return value === "asc" || value === "desc";
}

export function ListPage() {
  const [params, setParams] = useSearchParams();
  const qFromUrl = params.get("q") ?? "";
  const [q, setQ] = useState(qFromUrl);
  const platform = params.get("platform") ?? "";
  const sortParam = params.get("sort");
  const orderParam = params.get("order");
  const sort: GameSort = isSort(sortParam) ? sortParam : "metascore";
  const order: SortOrder = isOrder(orderParam) ? orderParam : "desc";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const selectedSort = `${sort}:${order}`;

  const patchParams = useCallback(
    (next: Record<string, string>, resetPage = true): void => {
      const merged = new URLSearchParams(params);
      for (const [key, value] of Object.entries(next)) {
        if (value) {
          merged.set(key, value);
        } else {
          merged.delete(key);
        }
      }
      if (resetPage) {
        merged.delete("page");
      }
      setParams(merged);
    },
    [params, setParams],
  );

  useEffect(() => {
    setQ(qFromUrl);
  }, [qFromUrl]);

  useEffect(() => {
    if (q === qFromUrl) {
      return;
    }
    const handle = window.setTimeout(() => {
      patchParams({ q: q.trim() });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [q, qFromUrl, patchParams]);

  const filters: GameListQuery = useMemo(
    () => ({
      q: qFromUrl.trim() || undefined,
      platform: platform || undefined,
      sort,
      order,
      page,
      page_size: 20,
    }),
    [qFromUrl, platform, sort, order, page],
  );

  const gamesQuery = useGamesQuery(filters);
  const platformsQuery = usePlatformsQuery();

  const total = gamesQuery.data?.meta.total ?? 0;
  const pageSize = gamesQuery.data?.meta.page_size ?? 20;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page">
      <header className="page-header">
        <h1>Game catalog</h1>
        <p className="lede">Search by title, filter by platform, and sort by rating.</p>
      </header>

      <form className="filters" onSubmit={(event) => event.preventDefault()}>
        <label className="field field--grow">
          <span className="field__label">Search</span>
          <input
            id="game-search"
            className="field__control"
            type="search"
            name="q"
            value={q}
            placeholder="Game title"
            autoComplete="off"
            onChange={(event) => {
              setQ(event.target.value);
            }}
          />
        </label>
        <PlatformFilter
          value={platform}
          platforms={platformsQuery.data?.items ?? []}
          disabled={platformsQuery.isPending}
          onChange={(value) => patchParams({ platform: value })}
        />
        <fieldset className="chip-field">
          <legend className="field__label">Sort</legend>
          <div className="chip-group">
            {SORT_OPTIONS.map((item) => (
              <button
                type="button"
                key={item.value}
                className={
                  selectedSort === item.value ? "chip chip--sort chip--selected" : "chip chip--sort"
                }
                aria-pressed={selectedSort === item.value}
                onClick={() =>
                  patchParams({
                    sort: item.sort,
                    order: item.order,
                  })
                }
              >
                {item.label}
              </button>
            ))}
          </div>
        </fieldset>
      </form>

      <div aria-busy={gamesQuery.isPending} aria-live="polite">
        {gamesQuery.isPending ? (
          <>
            <PageState kind="loading" title="Loading catalog..." />
            <SkeletonGrid />
          </>
        ) : null}
        {gamesQuery.isError ? (
          <PageState
            kind="error"
            title="Could not load the catalog"
            detail={gamesQuery.error instanceof Error ? gamesQuery.error.message : null}
            onRetry={() => void gamesQuery.refetch()}
          />
        ) : null}
        {gamesQuery.isSuccess && gamesQuery.data.items.length === 0 ? (
          <PageState kind="empty" title="No games yet">
            <p className="page-state__detail">
              <Link to="/monitor">Open the monitor and start a run</Link>
            </p>
          </PageState>
        ) : null}
        {gamesQuery.isSuccess && gamesQuery.data.items.length > 0 ? (
          <>
            <ul className="game-grid">
              {gamesQuery.data.items.map((game) => (
                <li key={game.metacritic_slug}>
                  <GameCard game={game} />
                </li>
              ))}
            </ul>
            {pageCount > 1 ? (
              <nav className="pagination" aria-label="Catalog pages">
                <button
                  type="button"
                  className="button"
                  disabled={page <= 1}
                  onClick={() => patchParams({ page: String(page - 1) }, false)}
                >
                  Previous
                </button>
                <p>
                  Page {page} of {pageCount}
                </p>
                <button
                  type="button"
                  className="button"
                  disabled={page >= pageCount}
                  onClick={() => patchParams({ page: String(page + 1) }, false)}
                >
                  Next
                </button>
              </nav>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
