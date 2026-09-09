import type { CollectionStateRead, ReviewSummary } from "../api/types";
import { CollectionSlot } from "./CollectionNotice";

type ReviewBlockProps = {
  heading: string;
  headingId: string;
  topic: string;
  summary: ReviewSummary | null | undefined;
  collection: CollectionStateRead | null | undefined;
};

function hasReviewCopy(summary: ReviewSummary | null | undefined): boolean {
  if (!summary) {
    return false;
  }
  return Boolean(summary.summary.trim() || summary.likes.length || summary.dislikes.length);
}

export function ReviewBlock({ heading, headingId, topic, summary, collection }: ReviewBlockProps) {
  return (
    <section className="panel" aria-labelledby={headingId}>
      <h2 id={headingId}>{heading}</h2>
      <CollectionSlot
        collection={collection}
        hasValue={hasReviewCopy(summary)}
        topic={topic}
        emptyTitle={`No ${topic.toLowerCase()} on Metacritic`}
      >
        {summary ? (
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
      </CollectionSlot>
    </section>
  );
}
