import { useState } from "react";

import { resolveMediaUrl } from "../api/media";

type CoverImageProps = {
  title: string;
  coverUrl: string | null | undefined;
  className?: string;
};

export function CoverImage({ title, coverUrl, className }: CoverImageProps) {
  const src = resolveMediaUrl(coverUrl);
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={className ? `cover cover--placeholder ${className}` : "cover cover--placeholder"} aria-hidden="true">
        <span>{title.slice(0, 1)}</span>
      </div>
    );
  }
  return (
    <img
      className={className ? `cover ${className}` : "cover"}
      src={src}
      alt={title}
      onError={() => setFailed(true)}
    />
  );
}
