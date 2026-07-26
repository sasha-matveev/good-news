import { useEffect, useState } from "react";

import {
  getDigest,
  listDigests,
  type DigestDetailRecord,
  type DigestListItemRecord
} from "../lib/api";
import { theme } from "../styles/theme";

type DigestsPageProps = {
  initialDigestId?: number | null;
  feedbackState?: string | null;
  postId?: number | null;
};

function formatDigestType(value: string) {
  const normalized = value.trim().toLowerCase();

  if (normalized === "daily") {
    return "Daily digest";
  }
  if (normalized === "weekly") {
    return "Weekly digest";
  }

  return normalized === "" ? "Unknown digest" : value;
}

function formatSentAt(value: string | null) {
  if (!value) {
    return "Not sent";
  }

  return value.replace("T", " ").replace(":00Z", " UTC").replace("Z", " UTC");
}

export function DigestsPage({
  initialDigestId = null,
  feedbackState = null,
  postId = null
}: DigestsPageProps) {
  const [digests, setDigests] = useState<DigestListItemRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDigestId, setSelectedDigestId] = useState<number | null>(initialDigestId);
  const [detail, setDetail] = useState<DigestDetailRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const nextDigests = await listDigests();
        if (!cancelled) {
          setDigests(nextDigests);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load digests.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedDigestId === null) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }

    const digestId = selectedDigestId;
    let cancelled = false;

    async function loadDetail() {
      setDetailLoading(true);
      try {
        const nextDetail = await getDigest(digestId);
        if (!cancelled) {
          setDetail(nextDetail);
          setDetailError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setDetail(null);
          setDetailError(loadError instanceof Error ? loadError.message : "Failed to load digest detail.");
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [selectedDigestId]);

  return (
    <section style={{ padding: "32px 24px 40px" }}>
      <div style={{ marginBottom: "24px" }}>
        <p
          style={{
            color: theme.color.muted,
            fontFamily: theme.font.sectionTitle,
            fontSize: "12px",
            letterSpacing: "0.16em",
            margin: 0,
            textTransform: "uppercase"
          }}
        >
          Digests
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Sent digest history
        </h2>
      </div>

      {feedbackState && postId !== null ? (
        <section
          style={{
            backgroundColor: theme.color.shell,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            marginBottom: "20px",
            padding: "14px 16px"
          }}
        >
          <strong>Feedback saved from digest email.</strong>
          <p style={{ margin: "8px 0 0" }}>
            Post {postId} is now marked as {feedbackState}.
          </p>
        </section>
      ) : null}

      {loading ? (
        <p>Loading digests...</p>
      ) : error ? (
        <div>
          <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
            {error}
          </p>
          <p>Sent digest history is unavailable right now.</p>
        </div>
      ) : digests.length === 0 ? (
        <div>
          <p>No sent digests exist yet.</p>
          <p>Sent digest history will appear here after the first delivery.</p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gap: "20px",
            gridTemplateColumns: "minmax(280px, 360px) minmax(0, 1fr)",
            alignItems: "start"
          }}
        >
          <div style={{ display: "grid", gap: "12px" }}>
            {digests.map((digest) => {
              const selected = digest.id === selectedDigestId;

              return (
                <button
                  aria-pressed={selected}
                  key={digest.id}
                  onClick={() => {
                    setSelectedDigestId(digest.id);
                  }}
                  style={{
                    backgroundColor: selected ? theme.color.shell : theme.color.card,
                    border: selected ? `1px solid ${theme.color.accent}` : `1px solid ${theme.color.border}`,
                    borderRadius: theme.radius.card,
                    cursor: "pointer",
                    display: "grid",
                    gap: "8px",
                    padding: "16px",
                    textAlign: "left"
                  }}
                  type="button"
                >
                  <strong>{formatSentAt(digest.sent_at)}</strong>
                  <span>Type: {formatDigestType(digest.digest_type)}</span>
                  <span>Included posts: {digest.included_post_count}</span>
                  <span
                    style={{
                      color: theme.color.accent,
                      fontFamily: theme.font.sectionTitle,
                      fontSize: "12px",
                      letterSpacing: "0.08em",
                      textTransform: "uppercase"
                    }}
                  >
                    View →
                  </span>
                </button>
              );
            })}
          </div>

          <div
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              display: "grid",
              gap: "16px",
              minHeight: "320px",
              padding: "20px"
            }}
          >
            {selectedDigestId === null ? (
              <p>Select a sent digest to inspect its stored content.</p>
            ) : detailLoading ? (
              <p>Loading digest detail...</p>
            ) : detailError ? (
              <div>
                <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
                  {detailError}
                </p>
                <p>Digest detail is unavailable right now.</p>
              </div>
            ) : !detail ? null : (
              <>
                <div>
                  <p
                    style={{
                      color: theme.color.muted,
                      fontFamily: theme.font.sectionTitle,
                      fontSize: "12px",
                      letterSpacing: "0.16em",
                      margin: 0,
                      textTransform: "uppercase"
                    }}
                  >
                    Stored detail
                  </p>
                  <h3 style={{ fontSize: "24px", margin: "12px 0 0" }}>{detail.title}</h3>
                </div>

                <div style={{ display: "grid", gap: "8px" }}>
                  <span>Type: {formatDigestType(detail.digest_type)}</span>
                  <span>Sent: {formatSentAt(detail.sent_at)}</span>
                </div>

                <div>
                  <h4 style={{ margin: "0 0 10px" }}>Included post titles</h4>
                  {detail.included_posts.length === 0 ? (
                    <p style={{ margin: 0 }}>No stored posts for this digest.</p>
                  ) : (
                    <ul style={{ margin: 0, paddingLeft: "20px" }}>
                      {detail.included_posts.map((post) => (
                        <li key={post.post_id} style={{ marginBottom: "6px" }}>
                          {post.title}
                          {post.feedback_state ? ` (${post.feedback_state})` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div style={{ display: "grid", gap: "10px" }}>
                  <h4 style={{ margin: 0 }}>Stored web version</h4>
                  <p style={{ color: theme.color.muted, margin: 0 }}>
                    Product-generated digest output preserved at send time.
                  </p>
                  <iframe
                    sandbox=""
                    srcDoc={detail.rendered_html}
                    style={{
                      backgroundColor: "#ffffff",
                      border: `1px solid ${theme.color.border}`,
                      borderRadius: theme.radius.card,
                      minHeight: "360px",
                      width: "100%"
                    }}
                    title="Rendered digest HTML web version"
                  />
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
