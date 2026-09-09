import { useState } from "react";

import { resolveMediaUrl } from "../api/media";
import type { CollectionStateRead } from "../api/types";
import { fieldState } from "../lib/collection";
import { CollectionNotice } from "./CollectionNotice";

type CoverImageProps = {
  title: string;
  coverUrl: string | null | undefined;
  collection?: CollectionStateRead | null;
  className?: string;
};

export function CoverImage({ title, coverUrl, collection, className }: CoverImageProps) {
  const src = resolveMediaUrl(coverUrl);
  const [failed, setFailed] = useState(false);
  const kind = failed ? "error" : fieldState(Boolean(src), collection);
  const classes = className ? `cover ${className}` : "cover";
  if (kind !== "ready" || !src) {
    const noticeKind = kind === "ready" ? "empty" : kind;
    return (
      <div className={`${classes} cover--notice`}>
        <CollectionNotice
          kind={noticeKind}
          layout="cover"
          title={
            noticeKind === "idle"
              ? "Cover has not been collected yet"
              : noticeKind === "loading"
                ? "Collecting cover"
                : noticeKind === "empty"
                  ? "No cover on Metacritic"
                  : "Could not load the cover"
          }
        />
      </div>
    );
  }
  return <img className={classes} src={src} alt={title} onError={() => setFailed(true)} />;
}
