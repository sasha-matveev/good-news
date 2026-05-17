import { useEffect, useState } from "react";

import { PostCard } from "../components/PostCard";
import { listPosts, type PostRecord, setReadLater } from "../lib/api";
import { theme } from "../styles/theme";

type WantToReadPageProps = {
  feedbackState?: string | null;
  postId?: number | null;
};

export function WantToReadPage({
  feedbackState = null,
  postId = null
}: WantToReadPageProps) {
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingPostId, setSavingPostId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const savedPosts = await listPosts({ window: "all", readLater: true });
        if (!cancelled) {
          setPosts(savedPosts);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load saved posts.");
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

  async function handleWantToReadToggle(postId: number, saved: boolean) {
    setSavingPostId(postId);
    try {
      await setReadLater(postId, saved);
      setPosts((currentPosts) =>
        saved
          ? currentPosts
          : currentPosts.filter((post) => post.id !== postId)
      );
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update saved posts.");
    } finally {
      setSavingPostId((current) => (current === postId ? null : current));
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
          Want To Read
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Saved posts waiting for a deeper read
        </h2>
      </div>

      {feedbackState === "want_to_read" && postId !== null ? (
        <section
          style={{
            backgroundColor: theme.color.shell,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            marginBottom: "20px",
            padding: "14px 16px"
          }}
        >
          <strong>Saved from digest email.</strong>
          <p style={{ margin: "8px 0 0" }}>
            Post {postId} was added to your want-to-read list.
          </p>
        </section>
      ) : null}

      {error ? (
        <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
          {error}
        </p>
      ) : null}

      {loading ? (
        <p>Loading saved posts...</p>
      ) : posts.length === 0 ? (
        <section
          style={{
            backgroundColor: theme.color.card,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            padding: "24px 20px"
          }}
        >
          <p
            style={{
              fontFamily: theme.font.sectionTitle,
              fontSize: "12px",
              letterSpacing: "0.12em",
              margin: 0,
              textTransform: "uppercase"
            }}
          >
            Empty
          </p>
          <p style={{ fontSize: "20px", lineHeight: 1.6, margin: "12px 0 0" }}>
            No saved posts yet.
          </p>
          <p style={{ margin: "12px 0 0" }}>
            Save posts from Feed when you want to come back and read them carefully.
          </p>
        </section>
      ) : (
        <div style={{ display: "grid", gap: "16px" }}>
          {posts.map((post) => (
            <PostCard
              busy={savingPostId === post.id}
              busyAction={savingPostId === post.id ? "remove" : null}
              key={post.id}
              onWantToReadToggle={handleWantToReadToggle}
              post={post}
            />
          ))}
        </div>
      )}
    </section>
  );
}
