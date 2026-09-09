import type { ReactNode } from "react";

import type { CollectionStateRead } from "../api/types";
import { collectionTitle, fieldState, type CollectionKind } from "../lib/collection";

type NoticeKind = Exclude<CollectionKind, "ready">;

type CollectionNoticeProps = {
  kind: NoticeKind;
  title: string;
  detail?: string | null;
  layout?: "block" | "cover" | "compact";
};

function IdleMark() {
  return (
    <svg className="collection-notice__mark" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="8" y="10" width="32" height="28" rx="6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeDasharray="5 4" />
      <circle cx="24" cy="24" r="7" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M24 20v5l3 2" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function LoadingMark() {
  return (
    <svg className="collection-notice__mark collection-notice__mark--spin" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r="14" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M38 24a14 14 0 0 0-14-14" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function EmptyMark() {
  return (
    <svg className="collection-notice__mark" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="9" y="16" width="30" height="20" rx="4" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M9 22h30" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M16 12h16l3 10H13l3-10z" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M18 28l12 8M30 28l-12 8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function ErrorMark() {
  return (
    <svg className="collection-notice__mark" viewBox="0 0 48 48" aria-hidden="true">
      <path d="M24 8l16 28H8L24 8z" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M24 20v8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="24" cy="32" r="1.6" fill="currentColor" />
    </svg>
  );
}

function Mark({ kind }: { kind: NoticeKind }) {
  if (kind === "idle") {
    return <IdleMark />;
  }
  if (kind === "loading") {
    return <LoadingMark />;
  }
  if (kind === "empty") {
    return <EmptyMark />;
  }
  return <ErrorMark />;
}

export function CollectionNotice({ kind, title, detail, layout = "block" }: CollectionNoticeProps) {
  const role = kind === "error" ? "alert" : "status";
  return (
    <div
      className={`collection-notice collection-notice--${kind} collection-notice--${layout}`}
      role={role}
      aria-live={kind === "loading" ? "polite" : undefined}
      aria-busy={kind === "loading" || undefined}
    >
      <Mark kind={kind} />
      <div className="collection-notice__copy">
        <p className="collection-notice__title">{title}</p>
        {detail ? <p className="collection-notice__detail">{detail}</p> : null}
      </div>
    </div>
  );
}

type CollectionSlotProps = {
  collection: CollectionStateRead | null | undefined;
  hasValue: boolean;
  topic: string;
  emptyTitle?: string;
  idleTitle?: string;
  loadingTitle?: string;
  errorTitle?: string;
  layout?: CollectionNoticeProps["layout"];
  children: ReactNode;
};

export function CollectionSlot({
  collection,
  hasValue,
  topic,
  emptyTitle,
  idleTitle,
  loadingTitle,
  errorTitle,
  layout = "block",
  children,
}: CollectionSlotProps) {
  const kind = fieldState(hasValue, collection);
  if (kind === "ready") {
    return children;
  }
  const titles: Record<NoticeKind, string> = {
    idle: idleTitle ?? collectionTitle("idle", topic),
    loading: loadingTitle ?? collectionTitle("loading", topic),
    empty: emptyTitle ?? collectionTitle("empty", topic),
    error: errorTitle ?? collectionTitle("error", topic),
  };
  return (
    <CollectionNotice
      kind={kind}
      title={titles[kind]}
      detail={kind === "error" ? collection?.error_message : null}
      layout={layout}
    />
  );
}
