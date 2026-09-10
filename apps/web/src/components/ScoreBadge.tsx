import type { CollectionStateRead } from "../api/types";
import { fieldState } from "../lib/collection";
import { formatUserscore, scoreTone } from "../lib/format";

type ScoreBadgeProps = {
  value: number | null | undefined;
  kind: "meta" | "user";
  label: string;
  collection?: CollectionStateRead | null;
  size?: "md" | "lg" | "hero";
};

export function ScoreBadge({ value, kind, label, collection, size = "md" }: ScoreBadgeProps) {
  const state = fieldState(value != null, collection);
  const sizeClass = size === "md" ? "" : ` score--${size}`;
  if (state !== "ready") {
    const text =
      state === "loading" ? "…" : state === "idle" ? "—" : state === "error" ? "!" : "n/a";
    const spoken =
      state === "loading"
        ? "collecting"
        : state === "idle"
          ? "not collected yet"
          : state === "error"
            ? "could not collect"
            : "not available";
    return (
      <span className={`score score--${state}${sizeClass}`} title={label} aria-label={`${label} ${spoken}`}>
        <span className="score__label">{label}</span>
        <span className="score__value">{text}</span>
      </span>
    );
  }
  const tone = scoreTone(value, kind);
  const text = kind === "user" ? formatUserscore(value) : String(value);
  return (
    <span className={`score score--${tone}${sizeClass}`} title={label} aria-label={`${label} ${text}`}>
      <span className="score__label">{label}</span>
      <span className="score__value">{text}</span>
    </span>
  );
}
