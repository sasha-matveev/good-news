import { useEffect, useState, type ReactNode } from "react";

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

const PAGE_LIMIT = 50;

/** A labelled cluster of related filter chips. */
function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <span
        style={{
          color: theme.color.muted,
          fontFamily: theme.font.sectionTitle,
          fontSize: "10px",
          fontWeight: 700,
          letterSpacing: "0.14em",
          textTransform: "uppercase"
        }}
      >
        {label}
      </span>
      <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: "8px" }}>
        {children}
      </div>
    </div>
  );
}

/** A single pill-shaped filter toggle, styled consistently across all groups. */
function FilterChip({
  active,
  busy = false,
  onClick,
  children
}: {
  active: boolean;
  busy?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      aria-pressed={active}
      disabled={busy}
      onClick={onClick}
      style={{
        backgroundColor: active ? theme.color.accent : theme.color.card,
        border: `1px solid ${active ? theme.color.accent : theme.color.border}`,
        borderRadius: theme.radius.card,
        color: active ? theme.color.card : theme.color.text,
        cursor: busy ? "wait" : "pointer",
        fontFamily: "inherit",
        fontSize: "12px",
        opacity: busy ? 0.7 : 1,
        padding: "8px 10px"
      }}
      type="button"
    >
      {children}
    </button>
  );
}

function buildRequestParams(filters: FeedFilterState, sort: PostSortMode, offset: number) {
  return {
    feedbackState: filters.feedbackState || undefined,
    sort,
    window: filters.window,
    limit: PAGE_LIMIT,
    offset: offset > 0 ? offset : undefined
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
  const [sort, setSort] = useState<PostSortMode>("date");
  const [pageOffset, setPageOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setPageOffset(0);
      try {
        const nextPosts = await listPosts(buildRequestParams(filters, sort, 0));
        if (!cancelled) {
          setPosts(nextPosts);
          setHasMore(nextPosts.length === PAGE_LIMIT);
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

  async function handleLoadMore() {
    const nextOffset = pageOffset + PAGE_LIMIT;
    setLoadingMore(true);
    try {
      const morePosts = await listPosts(buildRequestParams(filters, sort, nextOffset));
      setPosts((current) => [...current, ...morePosts]);
      setPageOffset(nextOffset);
      setHasMore(morePosts.length === PAGE_LIMIT);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load more posts.");
    } finally {
      setLoadingMore(false);
    }
  }

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
          {filters.feedbackState === "interesting"
            ? "Posts you liked"
            : filters.feedbackState === "not_interesting"
              ? "Posts you skipped"
              : filters.feedbackState === "none"
                ? "Posts awaiting your reaction"
                : "Your feed"}
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
            alignItems: "flex-start",
            display: "flex",
            flex: "1 1 auto",
            flexWrap: "wrap",
            gap: "20px"
          }}
        >
          <FilterGroup label="Reaction">
            {([
              { label: "All", value: "" },
              { label: "No reaction", value: "none" },
              { label: "Interesting", value: "interesting" },
              { label: "Not interesting", value: "not_interesting" }
            ] as const).map((chip) => (
              <FilterChip
                active={filters.feedbackState === chip.value}
                busy={loading}
                key={chip.value === "" ? "all" : chip.value}
                onClick={() => {
                  setFilters((current) => ({ ...current, feedbackState: chip.value }));
                }}
              >
                {chip.label}
              </FilterChip>
            ))}
          </FilterGroup>

          <FilterGroup label="Period">
            {([
              { label: "Last month", value: "last_month" as const },
              { label: "All time", value: "all" as const }
            ]).map((chip) => {
              const active = filters.window === chip.value;
              return (
                <FilterChip
                  active={active}
                  busy={loading}
                  key={chip.value}
                  onClick={() => {
                    setFilters((current) => ({ ...current, window: chip.value }));
                  }}
                >
                  {loading && active ? `Loading ${chip.label.toLowerCase()} posts...` : chip.label}
                </FilterChip>
              );
            })}
          </FilterGroup>
        </div>

        <div style={{ flexShrink: 0 }}>
          <FilterGroup label="Sort">
            {([
              { label: "By match", value: "match" },
              { label: "By date", value: "date" }
            ] as const).map((option) => (
              <FilterChip
                active={sort === option.value}
                busy={loading}
                key={option.value}
                onClick={() => {
                  setSort(option.value);
                }}
              >
                {option.label}
              </FilterChip>
            ))}
          </FilterGroup>
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
          <p>
            {filters.feedbackState || filters.window !== "all"
              ? "No posts match this filter."
              : "No collected posts yet."}
          </p>
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
          {hasMore ? (
            <div style={{ marginTop: "24px", textAlign: "center" }}>
              <button
                disabled={loadingMore}
                onClick={() => void handleLoadMore()}
                style={{
                  backgroundColor: theme.color.card,
                  border: `1px solid ${theme.color.border}`,
                  borderRadius: theme.radius.card,
                  color: theme.color.text,
                  cursor: loadingMore ? "wait" : "pointer",
                  fontFamily: "inherit",
                  fontSize: "14px",
                  opacity: loadingMore ? 0.7 : 1,
                  padding: "10px 24px"
                }}
                type="button"
              >
                {loadingMore ? "Loading..." : "Load more"}
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
