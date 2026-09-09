import type { LetsPlayRead, LetsPlayStatus } from "../api/types";

const STATUS_COPY: Record<LetsPlayStatus, string> = {
  ok: "",
  no_video: "No let's play was found on YouTube.",
  transcript_unavailable: "The video transcript is unavailable. The conclusion will appear later.",
  quota_exceeded: "The YouTube quota is exhausted. The conclusion will appear after the next quota window.",
};

export function letsPlayStatusText(status: LetsPlayStatus | null | undefined): string | null {
  if (!status || status === "ok") {
    return null;
  }
  return STATUS_COPY[status];
}

export function letsPlayPending(letsplay: LetsPlayRead | null | undefined): boolean {
  return letsplay == null;
}
