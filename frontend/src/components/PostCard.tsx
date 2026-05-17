import { useState } from "react";
import type { FeedbackState, PostRecord } from "../lib/api";
import { recordArticleOpen } from "../lib/api";
import { theme } from "../styles/theme";

function stripHtml(html: string): string {
  try {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return (doc.body.textContent ?? html).replace(/\s+/g, " ").trim();
  } catch {
    return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  }
}

function parseRankingExplanation(exp: string): Array<{ key: string; value: string }> {
  return exp.split(";").filter(Boolean).map((part) => {
    const [k, v] = part.split("=");
    return { key: k?.trim() ?? part, value: v?.trim() ?? "" };
  });
}

type PostCardProps = {
  busy?: boolean;
  busyAction?: "feedback" | "remove" | "readLater" | null;
  busyFeedbackState?: FeedbackState | null;
  onFeedbackSelect?: (postId: number, state: FeedbackState) => void;
  onReadLaterToggle?: (postId: number, saved: boolean) => void;
  onWantToReadToggle?: (postId: number, saved: boolean) => void;
  post: PostRecord;
};

const DATE_SOURCE_REASONS: Record<string, string> = {
  feed: "Date from feed",
  json_ld: "Date from page metadata (JSON-LD)",
  meta_og: "Date from page metadata (Open Graph)",
  meta_date: "Date from page metadata",
  time_element: "Date from page HTML",
  none: "No publication date found in the feed or article page",
};

type DateDisplay = { text: string; title: string; uncertain: boolean };

function formatPublishedDate(value: string | null, source: string | null): DateDisplay {
  const reason = (source && DATE_SOURCE_REASONS[source]) ?? "Date origin unknown";
  if (!value) {
    return {
      text: "Unknown date",
      title: reason,
      uncertain: true,
    };
  }
  const dateStr = value.split("T")[0] ?? value;
  return { text: dateStr, title: reason, uncertain: false };
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
  // Content values sum to ~0.5-2.5 for typical posts; multiply by 2 so
  // max non-feedback content score lands at ~5, feedback pushes toward 10.
  const total = feedbackScore + contentValues.reduce((sum, v) => sum + v, 0);
  return Math.max(0, Math.min(10, Math.round(total * 2)));
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
  const [logExpanded, setLogExpanded] = useState(false);
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
        {(() => {
          const date = formatPublishedDate(post.published_at, post.published_at_source);
          return (
            <div
              title={date.title}
              style={{
                color: date.uncertain ? "#a0aab4" : "#6a7480",
                fontSize: "12px",
                flexShrink: 0,
                cursor: "help",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              {date.uncertain && (
                <svg
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  viewBox="0 0 16 16"
                  style={{ width: "12px", height: "12px", flexShrink: 0 }}
                  aria-label="Date unavailable"
                >
                  <circle cx="8" cy="8" r="6.5" />
                  <path d="M8 5v3.5" strokeLinecap="round" />
                  <circle cx="8" cy="11" r="0.6" fill="currentColor" stroke="none" />
                </svg>
              )}
              {date.text}
            </div>
          );
        })()}
      </div>

      {/* Match score */}
      <div style={{ borderLeft: "4px solid #7ea3c6", paddingLeft: "10px", margin: "0 0 12px", fontSize: "13px", lineHeight: 1.4, color: "#4f6072" }}>
        <span style={{ color: theme.color.llm, fontWeight: 700 }}>
          match {buildMatchScore(post)}/10
        </span>
      </div>

      {/* LLM evaluation block — only when analysis exists */}
      {(post.summary_ru || post.verdict_reason) ? (() => {
        const summaryText = post.summary_ru ? stripHtml(post.summary_ru) : "";
        const verdictText = post.verdict_reason ? stripHtml(post.verdict_reason) : "";
        if (!summaryText && !verdictText) return null;
        return (
          <div style={{ margin: "0 0 12px", fontSize: "13px", lineHeight: 1.55 }}>
            {summaryText ? (
              <p style={{ margin: "0 0 4px" }}>{summaryText}</p>
            ) : null}
            {verdictText ? (
              <p style={{ margin: 0, color: theme.color.muted }}>{verdictText}</p>
            ) : null}
          </div>
        );
      })() : null}

      {/* Original content excerpt — always shown */}
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
        {stripHtml(post.raw_content)}
      </div>

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
              aria-label="Interesting"
              title="Interesting — boost similar posts"
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
              aria-label="OK / Neutral"
              title="OK — seen it, no strong opinion"
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
              aria-label="Not interesting"
              title="Not interesting — suppress similar posts"
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
              {/* Thumbs down — Feather Icons */}
              <svg fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ width: "15px", height: "15px" }}>
                <path d="M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9a2 2 0 002 2.3z" />
                <path d="M17 2h2.67A2.31 2.31 0 0122 4v7a2.31 2.31 0 01-2.33 2H17" />
              </svg>
            </button>
          ) : null}

          {/* Read later bookmark button */}
          {onReadLaterToggle ? (
            <button
              aria-label={post.read_later ? "Remove from Read Later" : "Save to Read Later"}
              title={post.read_later ? "Remove from Read Later" : "Save to Read Later"}
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

        {/* Analysis log toggle */}
        {post.ranking_explanation ? (
          <button
            type="button"
            onClick={() => { setLogExpanded((v) => !v); }}
            style={{
              background: "none",
              border: "none",
              color: theme.color.muted,
              cursor: "pointer",
              fontFamily: theme.font.sectionTitle,
              fontSize: "10px",
              letterSpacing: "0.1em",
              padding: "0 2px",
              textTransform: "uppercase"
            }}
          >
            {logExpanded ? "▲ hide analysis" : "▼ analysis log"}
          </button>
        ) : null}
      </div>

      {/* Analysis log terminal */}
      {logExpanded && post.ranking_explanation ? (() => {
        const parts = parseRankingExplanation(post.ranking_explanation);
        const score = buildMatchScore(post);
        return (
          <div style={{ marginTop: "10px", backgroundColor: "#111b27", border: "1px solid #1e3048", borderRadius: theme.radius.card, padding: "10px 14px", fontFamily: "'Consolas','Menlo','Monaco',monospace", fontSize: "11px", lineHeight: 1.7, color: "#c8dced" }}>
            <div style={{ color: "#2f5878", marginBottom: "4px" }}># post analysis — id {post.id}</div>
            {parts.map((p, i) => (
              <div key={i}>
                <span style={{ color: "#4a6d8c" }}>{p.key}</span>
                <span style={{ color: "#4a7095" }}>=</span>
                <span style={{ color: p.key === "feedback" ? "#7fbf8e" : "#c8dced" }}>{p.value || "—"}</span>
              </div>
            ))}
            <div style={{ borderTop: "1px solid #1e3048", marginTop: "6px", paddingTop: "6px", color: "#7fbf8e" }}>
              match score → {score}/10
            </div>
            {(post.verdict === "interesting" || post.verdict === "not_interesting") ? (
              <div style={{ color: "#7fbf8e" }}>verdict → {post.verdict}</div>
            ) : null}
            {post.verdict_reason ? (
              <div style={{ color: "#4a6d8c", marginTop: "2px" }}>{post.verdict_reason}</div>
            ) : null}
          </div>
        );
      })() : null}
    </article>
  );
}
