import { useEffect, useState } from "react";

import { PostCard } from "../components/PostCard";
import {
  listPosts,
  type PostSortMode,
  setReadLater,
  updateFeedback,
  type FeedbackState,
  type PostRecord
} from "../lib/api";
import { theme } from "../styles/theme";

type FeedFilterState = {
  feedbackState: string;
  window: "last_month" | "all";
};

function buildRequestParams(filters: FeedFilterState, sort: PostSortMode) {
  return {
    feedbackState: filters.feedbackState || undefined,
    sort,
    window: filters.window
  } as const;
}

export function FeedPage() {
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingPost, setSavingPost] = useState<{
    postId: number;
    state: FeedbackState;
  } | null>(null);
  const [readLaterBusy, setReadLaterBusy] = useState<number | null>(null);
  const [filters, setFilters] = useState<FeedFilterState>({
    feedbackState: "",
    window: "last_month"
  });
  const [sort, setSort] = useState<PostSortMode>("match");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const nextPosts = await listPosts(buildRequestParams(filters, sort));
        if (!cancelled) {
          setPosts(nextPosts);
          setError(null);
          setHasLoadedOnce(true);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load posts.");
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
  }, [filters, sort]);

  async function handleFeedbackSelect(postId: number, state: FeedbackState) {
    setSavingPost({ postId, state });
    try {
      const nextFeedbackState = (await updateFeedback(postId, state)).state;
      setPosts((currentPosts) =>
        currentPosts.map((post) =>
          post.id === postId
            ? { ...post, feedback_state: nextFeedbackState }
            : post
        )
      );
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save feedback.");
    } finally {
      setSavingPost((current) => (current?.postId === postId ? null : current));
    }
  }

  async function handleReadLaterToggle(postId: number, saved: boolean) {
    setReadLaterBusy(postId);
    try {
      const result = await setReadLater(postId, saved);
      setPosts((current) =>
        current.map((p) => (p.id === postId ? { ...p, read_later: result.read_later } : p))
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update Read Later.");
    } finally {
      setReadLaterBusy(null);
    }
  }

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
          Feed
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Collected posts ready for ranking
        </h2>
      </div>

      <div
        data-testid="feed-toolbar"
        style={{
          alignItems: "start",
          display: "flex",
          flexWrap: "wrap",
          gap: "16px",
          justifyContent: "space-between",
          marginBottom: "24px"
        }}
      >
        <div
          style={{
            alignItems: "center",
            display: "flex",
            flex: "1 1 auto",
            flexWrap: "wrap",
            gap: "8px"
          }}
        >
          {([
            { label: "All", value: "" },
            { label: "Interesting", value: "interesting" },
            { label: "Not interesting", value: "not_interesting" }
          ] as const).map((chip) => {
            const active = filters.feedbackState === chip.value;
            return (
              <button
                aria-pressed={active}
                disabled={loading}
                key={chip.value === "" ? "all" : chip.value}
                onClick={() => {
                  setFilters((current) => ({ ...current, feedbackState: chip.value }));
                }}
                style={{
                  backgroundColor: active ? theme.color.accent : theme.color.card,
                  border: `1px solid ${active ? theme.color.accent : theme.color.border}`,
                  borderRadius: theme.radius.card,
                  color: active ? theme.color.card : theme.color.text,
                  cursor: loading ? "wait" : "pointer",
                  fontFamily: "inherit",
                  fontSize: "12px",
                  opacity: loading ? 0.7 : 1,
                  padding: "8px 10px"
                }}
                type="button"
              >
                {chip.label}
              </button>
            );
          })}
          {([
            { label: "Last month", value: "last_month" as const },
            { label: "All time", value: "all" as const }
          ]).map((chip) => {
            const active = filters.window === chip.value;
            return (
              <button
                aria-pressed={active}
                disabled={loading}
                key={chip.value}
                onClick={() => {
                  setFilters((current) => ({ ...current, window: chip.value }));
                }}
                style={{
                  backgroundColor: active ? theme.color.accent : theme.color.card,
                  border: `1px solid ${active ? theme.color.accent : theme.color.border}`,
                  borderRadius: theme.radius.card,
                  color: active ? theme.color.card : theme.color.text,
                  cursor: loading ? "wait" : "pointer",
                  fontFamily: "inherit",
                  fontSize: "12px",
                  opacity: loading ? 0.7 : 1,
                  padding: "8px 10px"
                }}
                type="button"
              >
                {loading && active ? `Loading ${chip.label.toLowerCase()} posts...` : chip.label}
              </button>
            );
          })}
        </div>

        <div
          style={{
            alignItems: "center",
            display: "flex",
            flexShrink: 0,
            gap: "8px"
          }}
        >
          {([
            { label: "By match", value: "match" },
            { label: "By date", value: "date" }
          ] as const).map((option) => {
            const active = sort === option.value;
            return (
              <button
                aria-pressed={active}
                disabled={loading}
                key={option.value}
                onClick={() => {
                  setSort(option.value);
                }}
                style={{
                  backgroundColor: active ? theme.color.accent : theme.color.card,
                  border: `1px solid ${active ? theme.color.accent : theme.color.border}`,
                  borderRadius: theme.radius.card,
                  color: active ? theme.color.card : theme.color.text,
                  cursor: loading ? "wait" : "pointer",
                  fontFamily: "inherit",
                  fontSize: "12px",
                  opacity: loading ? 0.7 : 1,
                  padding: "8px 10px"
                }}
                type="button"
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {error ? (
        <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
          {error}
        </p>
      ) : null}

      {loading && !hasLoadedOnce ? (
        <p>Loading posts...</p>
      ) : posts.length === 0 ? (
        <>
          {loading ? <p role="status">Refreshing posts...</p> : null}
          <p>No collected posts yet.</p>
        </>
      ) : (
        <>
          {loading ? <p role="status">Refreshing posts...</p> : null}
          <div style={{ display: "grid", gap: "16px" }}>
            {posts.map((post) => (
              <PostCard
                busy={savingPost?.postId === post.id || readLaterBusy === post.id}
                busyAction={
                  readLaterBusy === post.id
                    ? "readLater"
                    : savingPost?.postId === post.id
                      ? "feedback"
                      : null
                }
                busyFeedbackState={savingPost?.postId === post.id ? savingPost.state : null}
                key={post.id}
                onFeedbackSelect={handleFeedbackSelect}
                onReadLaterToggle={handleReadLaterToggle}
                post={post}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
