import type { ReactNode } from "react";

type PageStateProps = {
  kind: "loading" | "empty" | "error";
  title: string;
  detail?: string | null;
  onRetry?: () => void;
  children?: ReactNode;
};

export function PageState({ kind, title, detail, onRetry, children }: PageStateProps) {
  return (
    <div className={`page-state page-state--${kind}`} role={kind === "error" ? "alert" : "status"} aria-live="polite">
      <p className="page-state__title">{title}</p>
      {detail ? <p className="page-state__detail">{detail}</p> : null}
      {children}
      {onRetry ? (
        <button type="button" className="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function SkeletonGrid() {
  return (
    <ul className="game-grid" aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => (
        <li key={index} className="skeleton-card">
          <div className="skeleton skeleton--cover" />
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line skeleton--short" />
        </li>
      ))}
    </ul>
  );
}
