import type { LetsPlayRead } from "../api/types";
import { letsPlayPending, letsPlayStatusText } from "../lib/letsplay";

type LetsPlayBlockProps = {
  letsplay: LetsPlayRead | null | undefined;
};

export function LetsPlayBlock({ letsplay }: LetsPlayBlockProps) {
  const statusText = letsPlayStatusText(letsplay?.status);
  return (
    <section className="panel" aria-labelledby="letsplay-heading">
      <h2 id="letsplay-heading">Let's play</h2>
      {letsPlayPending(letsplay) ? <p className="muted">Collecting let's play data.</p> : null}
      {statusText ? <p>{statusText}</p> : null}
      {letsplay?.video_url ? (
        <p>
          <a href={letsplay.video_url} rel="noreferrer" target="_blank">
            {letsplay.video_title || "Open on YouTube"}
          </a>
        </p>
      ) : null}
      {letsplay?.conclusion ? <p>{letsplay.conclusion}</p> : null}
      {letsplay?.highlights && letsplay.highlights.length > 0 ? (
        <ul>
          {letsplay.highlights.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
