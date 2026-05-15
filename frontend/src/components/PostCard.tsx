import type { FeedbackState, PostRecord } from "../lib/api";
import { recordArticleOpen } from "../lib/api";
import { theme } from "../styles/theme";

type PostCardProps = {
  busy?: boolean;
  busyAction?: "feedback" | "remove" | "readLater" | null;
  busyFeedbackState?: FeedbackState | null;
  onFeedbackSelect?: (postId: number, state: FeedbackState) => void;
  onReadLaterToggle?: (postId: number, saved: boolean) => void;
  onWantToReadToggle?: (postId: number, saved: boolean) => void;
  post: PostRecord;
};

function formatPublishedDate(value: string | null) {
  if (!value) {
    return "Unknown date";
  }

  return value.split("T")[0] ?? value;
}

// Keep in sync with FEEDBACK_WEIGHTS in backend/app/services/ranking.py
const FEEDBACK_SCORE: Partial<Record<string, number>> = {
  interesting: 4.0,
  want_to_read: 5.0,
  not_interesting: -4.0,
};

export function buildMatchScore(post: PostRecord): number {
  const exp = post.ranking_explanation ?? "";
  const feedbackLabel = exp.match(/feedback=([^;]+)/)?.[1]?.trim() ?? "";
  const feedbackScore = FEEDBACK_SCORE[feedbackLabel] ?? 0;
  const contentValues = Array.from(exp.matchAll(/=([0-9.]+)/g)).map(
    (match) => Number.parseFloat(match[1] ?? "0")
  );
  const total = feedbackScore + contentValues.reduce((sum, v) => sum + v, 0);
  return Math.max(0, Math.min(10, Math.round(total * 10)));
}

export function PostCard({
  busy = false,
  busyAction = null,
  busyFeedbackState: _busyFeedbackState = null,
  onFeedbackSelect,
  onReadLaterToggle,
  onWantToReadToggle,
  post
}: PostCardProps) {
  const canRemoveFromWantToRead =
    post.read_later === true && onWantToReadToggle !== undefined;


  return (
    <article
      style={{
        backgroundColor: theme.color.card,
        border: `1px solid ${theme.color.border}`,
        borderRadius: theme.radius.card,
        boxShadow: "0 12px 24px rgba(25, 34, 43, 0.08)",
        padding: "20px"
      }}
    >
      {/* Fix 1: post-top layout — source + title on left, date on right */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "flex-start", marginBottom: "10px" }}>
        <div>
          <div style={{
            color: "#738194",
            fontFamily: theme.font.sectionTitle,
            fontSize: "12px",
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            marginBottom: "6px"
          }}>
            {post.source_name ?? "Unknown source"}
          </div>
          <h3 style={{ fontSize: "21px", letterSpacing: "-0.02em", margin: 0, lineHeight: 1.16 }}>
            {post.title}
          </h3>
        </div>
        <div style={{ color: "#6a7480", fontSize: "12px", flexShrink: 0 }}>
          {formatPublishedDate(post.published_at)}
        </div>
      </div>

      {/* Fix 2: LLM line — bold score + dot separator + reason */}
      <div style={{ borderLeft: "4px solid #7ea3c6", paddingLeft: "10px", margin: "0 0 14px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px", fontSize: "13px", lineHeight: 1.4, color: "#4f6072" }}>
        <span style={{ color: theme.color.llm, fontWeight: 700 }}>
          match {buildMatchScore(post)}/10
        </span>
        {post.verdict_reason ? (
          <>
            <span aria-hidden="true" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#8fa8bf", display: "inline-block" }} />
            <span>{post.verdict_reason}</span>
          </>
        ) : null}
      </div>

      {post.summary_ru ? <p style={{ margin: "0 0 14px" }}>{post.summary_ru}</p> : null}
      {!post.summary_ru ? (
        <div style={{
          borderTop: `1px solid ${theme.color.border}`,
          color: theme.color.muted,
          display: "-webkit-box",
          fontSize: "13px",
          lineHeight: 1.55,
          margin: "0 0 14px",
          overflow: "hidden",
          paddingTop: "10px",
          WebkitBoxOrient: "vertical",
          WebkitLineClamp: 3
        }}>
          {post.raw_content}
        </div>
      ) : null}

      {/* Fix 3: Actions row — icon buttons + correct order */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", paddingTop: "4px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
          {/* Read article link — first */}
          <a
            href={post.canonical_url}
            rel="noreferrer"
            onClick={() => { void recordArticleOpen(post.id); }}
            style={{
              backgroundColor: "#eef4f9",
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              color: theme.color.accent,
              display: "inline-block",
              fontFamily: theme.font.sectionTitle,
              fontSize: "12px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              padding: "8px 14px",
              textDecoration: "none",
              textTransform: "uppercase"
            }}
            target="_blank"
          >
            Read article
            <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "13px", height: "13px", marginLeft: "5px", verticalAlign: "middle" }}>
              <path d="M6 3h7v7" /><path d="M5 11L13 3" /><path d="M3 5v8h8" />
            </svg>
          </a>

          {/* Like button */}
          {onFeedbackSelect ? (
            <button
              aria-label="Like"
              aria-pressed={post.feedback_state === "interesting"}
              disabled={busy}
              onClick={() => {
                onFeedbackSelect(post.id, "interesting");
              }}
              style={{
                width: "34px",
                height: "34px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${post.feedback_state === "interesting" ? theme.color.accent : theme.color.border}`,
                backgroundColor: post.feedback_state === "interesting" ? theme.color.accent : theme.color.card,
                color: post.feedback_state === "interesting" ? theme.color.card : theme.color.text,
                borderRadius: theme.radius.card,
                cursor: busy ? "wait" : "pointer",
                opacity: busy ? 0.7 : 1,
                padding: 0
              }}
              type="button"
            >
              <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                <path d="M8 13s-4.5-2.8-4.5-6.1A2.4 2.4 0 018 5.1a2.4 2.4 0 014.5 1.8C12.5 10.2 8 13 8 13z" />
              </svg>
            </button>
          ) : null}

          {/* Norm button */}
          {onFeedbackSelect ? (
            <button
              aria-label="Norm"
              aria-pressed={post.feedback_state === "norm"}
              disabled={busy}
              onClick={() => { onFeedbackSelect(post.id, "norm"); }}
              style={{
                width: "34px",
                height: "34px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${post.feedback_state === "norm" ? theme.color.accent : theme.color.border}`,
                backgroundColor: post.feedback_state === "norm" ? theme.color.accent : theme.color.card,
                color: post.feedback_state === "norm" ? theme.color.card : theme.color.text,
                borderRadius: theme.radius.card,
                cursor: busy ? "wait" : "pointer",
                opacity: busy ? 0.7 : 1,
                padding: 0
              }}
              type="button"
            >
              <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                <path d="M4 8h8" />
              </svg>
            </button>
          ) : null}

          {/* Dislike button */}
          {onFeedbackSelect ? (
            <button
              aria-label="Dislike"
              aria-pressed={post.feedback_state === "not_interesting"}
              disabled={busy}
              onClick={() => {
                onFeedbackSelect(post.id, "not_interesting");
              }}
              style={{
                width: "34px",
                height: "34px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${post.feedback_state === "not_interesting" ? theme.color.accent : theme.color.border}`,
                backgroundColor: post.feedback_state === "not_interesting" ? theme.color.accent : theme.color.card,
                color: post.feedback_state === "not_interesting" ? theme.color.card : theme.color.text,
                borderRadius: theme.radius.card,
                cursor: busy ? "wait" : "pointer",
                opacity: busy ? 0.7 : 1,
                padding: 0
              }}
              type="button"
            >
              <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                <path d="M8 3s4.5 2.8 4.5 6.1A2.4 2.4 0 018 10.9a2.4 2.4 0 01-4.5-1.8C3.5 5.8 8 3 8 3z" />
              </svg>
            </button>
          ) : null}

          {/* Read later bookmark button */}
          {onReadLaterToggle ? (
            <button
              aria-label={post.read_later ? "Remove from Read Later" : "Add to Read Later"}
              aria-pressed={post.read_later}
              disabled={busy}
              onClick={() => {
                onReadLaterToggle(post.id, !post.read_later);
              }}
              style={{
                width: "34px",
                height: "34px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${post.read_later ? theme.color.accent : theme.color.border}`,
                backgroundColor: post.read_later ? theme.color.accent : theme.color.card,
                color: post.read_later ? theme.color.card : "#876e46",
                borderRadius: theme.radius.card,
                cursor: busy ? "wait" : "pointer",
                opacity: busy ? 0.7 : 1,
                padding: 0
              }}
              type="button"
            >
              <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                <path d="M4 3.5h8v10l-4-2.5-4 2.5z" />
              </svg>
            </button>
          ) : null}

          {/* WantToRead remove button (shown on WantToReadPage) */}
          {canRemoveFromWantToRead ? (
            <button
              disabled={busy}
              onClick={() => {
                onWantToReadToggle?.(post.id, false);
              }}
              style={{
                backgroundColor: theme.color.card,
                border: `1px solid ${theme.color.border}`,
                borderRadius: theme.radius.card,
                color: theme.color.text,
                cursor: busy ? "wait" : "pointer",
                fontFamily: "inherit",
                opacity: busy ? 0.7 : 1,
                padding: "8px 12px"
              }}
              type="button"
            >
              {busy && busyAction === "remove" ? "Removing..." : "Remove from want to read"}
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}
