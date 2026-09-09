import type { ReviewSummary } from "../api/types";

type ReviewBlockProps = {
  heading: string;
  headingId: string;
  summary: ReviewSummary | null | undefined;
};

function hasReviewCopy(summary: ReviewSummary | null | undefined): boolean {
  if (!summary) {
    return false;
  }
  return Boolean(summary.summary.trim() || summary.likes.length || summary.dislikes.length);
}

export function ReviewBlock({ heading, headingId, summary }: ReviewBlockProps) {
  const collecting = summary == null;
  const empty = summary != null && !hasReviewCopy(summary);
  return (
    <section className="panel" aria-labelledby={headingId}>
      <h2 id={headingId}>{heading}</h2>
      {collecting ? <p className="muted">Collecting reviews.</p> : null}
      {empty ? <p className="muted">No reviews yet.</p> : null}
      {hasReviewCopy(summary) && summary ? (
        <>
          {summary.summary.trim() ? <p>{summary.summary}</p> : null}
          {summary.likes.length > 0 ? (
            <p>
              <strong>Likes: </strong>
              {summary.likes.join(", ")}
            </p>
          ) : null}
          {summary.dislikes.length > 0 ? (
            <p>
              <strong>Dislikes: </strong>
              {summary.dislikes.join(", ")}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
