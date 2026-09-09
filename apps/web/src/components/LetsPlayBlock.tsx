import type { CollectionStateRead, LetsPlayRead } from "../api/types";
import { CollectionSlot } from "./CollectionNotice";

type LetsPlayBlockProps = {
  letsplay: LetsPlayRead | null | undefined;
  collection: CollectionStateRead | null | undefined;
};

export function LetsPlayBlock({ letsplay, collection }: LetsPlayBlockProps) {
  const hasVideo = Boolean(letsplay?.video_url);
  const hasConclusion = Boolean(letsplay?.conclusion?.trim());
  const emptyTitle =
    letsplay?.status === "transcript_unavailable"
      ? "The video has no usable transcript"
      : "No let's play was found on YouTube";
  const body = (
    <CollectionSlot
      collection={collection}
      hasValue={hasConclusion}
      topic="Let's play"
      emptyTitle={emptyTitle}
      idleTitle="Let's play has not been collected yet"
      loadingTitle="Looking for a let's play"
      errorTitle="Could not collect let's play"
    >
      {letsplay?.conclusion ? <p>{letsplay.conclusion}</p> : null}
      {letsplay?.highlights && letsplay.highlights.length > 0 ? (
        <ul>
          {letsplay.highlights.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </CollectionSlot>
  );
  return (
    <section className="panel" aria-labelledby="letsplay-heading">
      <h2 id="letsplay-heading">Let's play</h2>
      {hasVideo ? (
        <>
          <p>
            <a href={letsplay?.video_url ?? undefined} rel="noreferrer" target="_blank">
              {letsplay?.video_title || "Open on YouTube"}
            </a>
          </p>
          {body}
        </>
      ) : (
        body
      )}
    </section>
  );
}
