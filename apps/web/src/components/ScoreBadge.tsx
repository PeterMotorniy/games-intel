import { formatUserscore, scoreTone } from "../lib/format";

type ScoreBadgeProps = {
  value: number | null | undefined;
  kind: "meta" | "user";
  label: string;
};

export function ScoreBadge({ value, kind, label }: ScoreBadgeProps) {
  const tone = scoreTone(value, kind);
  const text = kind === "user" ? formatUserscore(value) : value == null ? "n/a" : String(value);
  return (
    <span className={`score score--${tone}`} title={label} aria-label={`${label} ${text}`}>
      <span className="score__label">{label}</span>
      <span className="score__value">{text}</span>
    </span>
  );
}
