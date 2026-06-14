import React, { useEffect, useRef, useState } from "react";

// v2 – inline terminals per source card
import { theme } from "../styles/theme";

import { SourceForm } from "../components/SourceForm";
import { SourceIcon } from "../components/SourceIcon";
import {
  createSource,
  deleteSource,
  getSourceLog,
  listSources,
  reloadPosts,
  runSourceSyncOnce,
  syncSource,
  SourceLogLine,
  SourceRecord,
  updateSourceActive
} from "../lib/api";

function sourceTitle(source: SourceRecord) {
  return source.display_name ?? source.original_url;
}

function timeAgo(value: string | null | undefined): string {
  if (!value) return "Never";
  const diffMs = Date.now() - new Date(value).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatLogTime(ts: number): string {
  const d = new Date(ts * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; color: string; label: string }> = {
    ready:              { bg: "#e8f3ec", color: "#3a6b4a", label: "Ready" },
    discovering:        { bg: "#e8f0f8", color: "#2f5878", label: "Discovering…" },
    needs_readaptation: { bg: "#fdf3e3", color: "#7a5c2a", label: "Needs readaptation" },
    failed:             { bg: "#faeae8", color: "#7f2f1d", label: "Failed" },
    failing:            { bg: "#faeae8", color: "#c47060", label: "Failing" },
    pending:            { bg: "#f0f0f0", color: "#666",    label: "Pending" },
  };
  const c = cfg[status] ?? { bg: "#f0f0f0", color: "#666", label: status };
  return (
    <span style={{
      backgroundColor: c.bg,
      borderRadius: "3px",
      color: c.color,
      display: "inline-block",
      fontFamily: theme.font.sectionTitle,
      fontSize: "11px",
      fontWeight: 700,
      letterSpacing: "0.08em",
      padding: "3px 8px",
      textTransform: "uppercase"
    }}>
      {c.label}
    </span>
  );
}

type ActiveLog = {
  sourceId: number;
  lines: SourceLogLine[];
  done: boolean;
  finalStatus: string | null;
};

function iconBtn(active: boolean, activeColor?: string, activeBg?: string): React.CSSProperties {
  return {
    width: "32px",
    height: "32px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: active ? (activeBg ?? "#eef4f9") : theme.color.card,
    border: `1px solid ${active ? (activeColor ?? theme.color.accent) : theme.color.border}`,
    borderRadius: theme.radius.card,
    color: active ? (activeColor ?? theme.color.accent) : theme.color.muted,
    cursor: "pointer",
    padding: 0,
    flexShrink: 0,
  };
}

type PendingAction =
  | { type: "add" }
  | { type: "sync" }
  | { type: "syncSource"; sourceId: number }
  | { type: "reloadPosts"; sourceId: number }
  | { type: "toggle"; sourceId: number }
  | { type: "delete"; sourceId: number }
  | null;

export function SourcesPage() {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [activeLog, setActiveLog] = useState<ActiveLog | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const saving = pendingAction !== null;

  const hasDiscovering = sources.some((s) => s.status === "discovering");

  async function reloadSources() {
    const next = await listSources();
    setSources(next);
  }

  // Initial load
  useEffect(() => {
    let cancelled = false;
    listSources()
      .then((data) => { if (!cancelled) { setSources(data); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load sources."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Auto-poll while any source is "discovering" — catches page reloads too
  useEffect(() => {
    if (!hasDiscovering) return;
    const interval = setInterval(() => { void reloadSources(); }, 2000);
    return () => { clearInterval(interval); };
  }, [hasDiscovering]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll the discovery log for the active terminal
  useEffect(() => {
    if (!activeLog || activeLog.done) return;
    const interval = setInterval(() => {
      void (async () => {
        try {
          const result = await getSourceLog(activeLog.sourceId);
          setActiveLog((prev) =>
            prev ? { ...prev, lines: result.log, done: result.done, finalStatus: result.status } : null
          );
          if (result.done) {
            await reloadSources();
          }
        } catch { /* ignore transient errors */ }
      })();
    }, 1500);
    return () => { clearInterval(interval); };
  }, [activeLog?.sourceId, activeLog?.done]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll terminal to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [activeLog?.lines.length]);

  async function handleAddSource(url: string) {
    setPendingAction({ type: "add" });
    setActiveLog(null);
    try {
      const created = await createSource(url);
      setSources((curr) => [...curr, created]);
      setError(null);
      setSyncStatus(null);
      setActiveLog({ sourceId: created.id, lines: [], done: created.status !== "discovering", finalStatus: created.status });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add source.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleToggle(source: SourceRecord) {
    setPendingAction({ type: "toggle", sourceId: source.id });
    try {
      const updated = await updateSourceActive(source.id, !source.active);
      setSources((curr) => curr.map((s) => s.id === updated.id ? updated : s));
      setError(null);
      setSyncStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update source.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleDelete(source: SourceRecord) {
    setPendingAction({ type: "delete", sourceId: source.id });
    setConfirmDeleteId(null);
    try {
      await deleteSource(source.id);
      setSources((curr) => curr.filter((s) => s.id !== source.id));
      setError(null);
      setSyncStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete source.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSync() {
    setPendingAction({ type: "sync" });
    try {
      const result = await runSourceSyncOnce();
      await reloadSources();
      const n = result.processed_source_ids.length;
      setSyncStatus(n === 0 ? "Sync complete. No active sources processed." : `Sync complete for ${n} source${n === 1 ? "" : "s"}.`);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to sync sources.");
      setSyncStatus(null);
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSyncSource(source: SourceRecord) {
    setPendingAction({ type: "syncSource", sourceId: source.id });
    const start = Date.now() / 1000;
    setActiveLog({
      sourceId: source.id,
      lines: [{ ts: start, msg: `Syncing ${sourceTitle(source)}…` }],
      done: false,
      finalStatus: null
    });
    try {
      const result = await syncSource(source.id);
      const next = await listSources();
      setSources(next);
      const updated = next.find((s) => s.id === source.id);
      const wasProcessed = result.processed_source_ids.includes(source.id);
      const end = Date.now() / 1000;

      let endMsg: string;
      let finalStatus = updated?.status ?? "ready";

      if (!wasProcessed) {
        endMsg = "Source was not processed — it may be inactive.";
      } else if (updated?.needs_readaptation) {
        endMsg = `Sync failed: ${updated.readaptation_reason ?? "strategy needs update."}`;
        finalStatus = "needs_readaptation";
      } else {
        const newPosts = (updated?.post_count ?? 0) - source.post_count;
        endMsg = newPosts > 0
          ? `Sync complete — ${newPosts} new post${newPosts === 1 ? "" : "s"} fetched.`
          : "Sync complete — 0 new posts.";
      }

      setActiveLog((prev) => prev ? {
        ...prev,
        lines: [...prev.lines, { ts: end, msg: endMsg }],
        done: true,
        finalStatus
      } : null);
      setError(null);
    } catch (e) {
      const end = Date.now() / 1000;
      const msg = e instanceof Error ? e.message : "Sync failed.";
      setActiveLog((prev) => prev ? {
        ...prev,
        lines: [...prev.lines, { ts: end, msg: `Error: ${msg}` }],
        done: true,
        finalStatus: "failed"
      } : null);
      setError(msg);
    } finally {
      setPendingAction(null);
    }
  }

  async function handleReloadPosts(source: SourceRecord) {
    const confirmed = window.confirm(
      `Reload posts for ${sourceTitle(source)}?\n\n` +
      "This will delete and reload posts from the last 2 months for this source. " +
      "Post age is determined by published date when available, otherwise by the date the post was added."
    );
    if (!confirmed) return;

    setPendingAction({ type: "reloadPosts", sourceId: source.id });
    const start = Date.now() / 1000;
    setActiveLog({
      sourceId: source.id,
      lines: [{ ts: start, msg: `Reloading recent posts for ${sourceTitle(source)}…` }],
      done: false,
      finalStatus: null,
    });
    try {
      const result = await reloadPosts(source.id);
      await reloadSources();
      const end = Date.now() / 1000;
      const msg = `Deleted ${result.deleted} recent post${result.deleted === 1 ? "" : "s"}. Reloaded ${result.reloaded} post${result.reloaded === 1 ? "" : "s"} from the source.`;
      setActiveLog((prev) => prev
        ? { ...prev, lines: [...prev.lines, { ts: end, msg }], done: true, finalStatus: "ready" }
        : null
      );
      setError(null);
    } catch (e) {
      const end = Date.now() / 1000;
      const msg = e instanceof Error ? e.message : "Reload failed.";
      setActiveLog((prev) => prev
        ? { ...prev, lines: [...prev.lines, { ts: end, msg: `Error: ${msg}` }], done: true, finalStatus: "failed" }
        : null
      );
      setError(msg);
    } finally {
      setPendingAction(null);
    }
  }

  async function handleShowLog(source: SourceRecord) {
    // Toggle: if this source's log is already shown, hide it
    if (activeLog?.sourceId === source.id) {
      setActiveLog(null);
      return;
    }
    try {
      const result = await getSourceLog(source.id);
      let lines = result.log;

      // When in-memory log is empty (e.g. server restarted), synthesise lines from source metadata
      if (lines.length === 0) {
        const now = Date.now() / 1000;
        lines = [
          { ts: now, msg: "No in-memory log — server may have restarted." },
          { ts: now, msg: `status: ${result.status ?? source.status}` },
          { ts: now, msg: `strategy: ${source.strategy_kind ?? "unknown"}` },
          { ts: now, msg: `last_success: ${source.last_success_at ?? "never"}` },
          { ts: now, msg: `last_failure: ${source.last_failure_at ?? "none"}` },
          ...(source.needs_readaptation
            ? [{ ts: now, msg: `readaptation: ${source.readaptation_reason ?? "no reason recorded"}` }]
            : []),
        ];
      }

      setActiveLog({ sourceId: source.id, lines, done: result.done, finalStatus: result.status });
    } catch {
      setActiveLog({ sourceId: source.id, lines: [], done: true, finalStatus: source.status });
    }
  }

  const logStatusColor = (s: string | null) => {
    if (s === "ready") return "#4a7c59";
    if (s === "failed" || s === "failing") return "#9b3a2d";
    if (s === "needs_readaptation") return "#876e46";
    return theme.color.muted;
  };

  return (
    <section style={{ padding: "32px 24px 40px" }}>
      <div style={{ marginBottom: "24px" }}>
        <p style={{ color: theme.color.muted, fontFamily: theme.font.sectionTitle, fontSize: "12px", letterSpacing: "0.16em", margin: 0, textTransform: "uppercase" }}>
          Sources
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>Manage your content sources</h2>
      </div>

      <SourceForm
        disabled={saving}
        onSubmit={handleAddSource}
        submitLabel={pendingAction?.type === "add" ? "Adding source..." : "Add source"}
      />

      <div style={{ marginBottom: "16px" }}>
        <button
          type="button"
          disabled={saving || loading || sources.filter((s) => s.status !== "discovering").length === 0}
          onClick={() => { void handleSync(); }}
          style={{
            backgroundColor: theme.color.accent,
            border: `1px solid ${theme.color.accent}`,
            borderRadius: theme.radius.card,
            color: "#ffffff",
            cursor: "pointer",
            fontFamily: "inherit",
            padding: "10px 16px"
          }}
        >
          {pendingAction?.type === "sync" ? "Syncing sources..." : "Sync sources now"}
        </button>
      </div>

      {error ? <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>{error}</p> : null}
      {syncStatus ? <p style={{ color: "#3a6b4a" }}>{syncStatus}</p> : null}

      {loading ? (
        <p>Loading sources…</p>
      ) : sources.length === 0 ? (
        <p>No sources yet.</p>
      ) : (
        <div style={{ display: "grid", gap: "12px" }}>
          {sources.map((source) => {
            const isDiscovering = source.status === "discovering";
            const syncNeeded = source.status === "ready" && source.post_count === 0 && !source.last_success_at;

            return (
              <article
                key={source.id}
                style={{
                  backgroundColor: theme.color.card,
                  border: `1px solid ${isDiscovering ? "#4a7095" : theme.color.border}`,
                  borderRadius: theme.radius.card,
                  padding: "16px 20px"
                }}
              >
                {/* Row 1: title + actions */}
                <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "flex-start", marginBottom: "10px" }}>
                  <div style={{ display: "flex", gap: "12px", alignItems: "center", minWidth: 0 }}>
                    <SourceIcon url={source.original_url} size={24} title={sourceTitle(source)} />
                    <div style={{ minWidth: 0 }}>
                      <h3 style={{ fontSize: "18px", margin: "0 0 3px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {sourceTitle(source)}
                      </h3>
                      <a
                        href={source.original_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: theme.color.muted, fontSize: "12px", textDecoration: "none" }}
                      >
                        {source.original_url}
                      </a>
                    </div>
                  </div>

                  {/* Actions — icon button groups */}
                  <div style={{ display: "flex", gap: "6px", alignItems: "flex-start", flexShrink: 0 }}>
                    {/* Group 1: sync + reload posts + log */}
                    {!isDiscovering && (
                      <>
                        <button
                          type="button"
                          disabled={saving}
                          title="Sync this source now"
                          aria-label={`Sync ${sourceTitle(source)}`}
                          onClick={() => { void handleSyncSource(source); }}
                          style={iconBtn(pendingAction?.type === "syncSource" && pendingAction.sourceId === source.id)}
                        >
                          {pendingAction?.type === "syncSource" && pendingAction.sourceId === source.id ? (
                            <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px", animation: "spin 1s linear infinite" }}>
                              <path d="M8 2a6 6 0 11-4.24 10.24" />
                            </svg>
                          ) : (
                            /* refresh-cw (two arrows) — fetch new posts */
                            <svg fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ width: "15px", height: "15px" }}>
                              <polyline points="23 4 23 10 17 10" />
                              <polyline points="1 20 1 14 7 14" />
                              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          disabled={saving}
                          title="Reload posts — delete and re-fetch posts from the last 2 months for this source"
                          aria-label={`Reload posts for ${sourceTitle(source)}`}
                          onClick={() => { void handleReloadPosts(source); }}
                          style={iconBtn(pendingAction?.type === "reloadPosts" && pendingAction.sourceId === source.id, "#5a7a5a", "#eef4ee")}
                        >
                          {pendingAction?.type === "reloadPosts" && pendingAction.sourceId === source.id ? (
                            <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px", animation: "spin 1s linear infinite" }}>
                              <path d="M8 2a6 6 0 11-4.24 10.24" />
                            </svg>
                          ) : (
                            /* download-into-tray — delete and re-fetch posts (distinct from plain sync) */
                            <svg fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ width: "15px", height: "15px" }}>
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                              <polyline points="7 10 12 15 17 10" />
                              <line x1="12" y1="3" x2="12" y2="15" />
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          title="View source log"
                          aria-label={`Log for ${sourceTitle(source)}`}
                          onClick={() => { void handleShowLog(source); }}
                          style={iconBtn(activeLog?.sourceId === source.id, "#2f5878", "#eef4f9")}
                        >
                          <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                            <path d="M3 4h10M3 8h8M3 12h6" />
                          </svg>
                        </button>
                      </>
                    )}

                    {/* Separator */}
                    {!isDiscovering && <div style={{ width: "1px", background: theme.color.border, alignSelf: "stretch", margin: "2px 0" }} />}

                    {/* Group 2: enable/disable */}
                    {isDiscovering ? (
                      <span style={{ color: "#4a7095", fontFamily: theme.font.sectionTitle, fontSize: "11px", letterSpacing: "0.1em", padding: "8px 4px", textTransform: "uppercase" }}>
                        Discovering…
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={saving}
                        title={source.active ? `Disable ${sourceTitle(source)}` : `Enable ${sourceTitle(source)}`}
                        aria-label={source.active ? `Disable ${sourceTitle(source)}` : `Enable ${sourceTitle(source)}`}
                        onClick={() => { void handleToggle(source); }}
                        style={iconBtn(false, source.active ? theme.color.muted : theme.color.accent)}
                      >
                        {pendingAction?.type === "toggle" && pendingAction.sourceId === source.id ? (
                          <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                            <circle cx="8" cy="8" r="2" />
                          </svg>
                        ) : source.active ? (
                          /* Pause icon — source is active, click to disable */
                          <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                            <path d="M6 4v8M10 4v8" />
                          </svg>
                        ) : (
                          /* Play icon — source is inactive, click to enable */
                          <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                            <path d="M5 3l8 5-8 5z" />
                          </svg>
                        )}
                      </button>
                    )}

                    {/* Group 3: delete */}
                    {confirmDeleteId === source.id ? (
                      <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", color: "#7f2f1d", fontFamily: theme.font.sectionTitle, letterSpacing: "0.06em" }}>Delete?</span>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => { void handleDelete(source); }}
                          style={{ ...iconBtn(false, "#9b3a2d"), backgroundColor: "#9b3a2d", color: "#fff" }}
                          title="Confirm delete"
                        >
                          {pendingAction?.type === "delete" && pendingAction.sourceId === source.id ? (
                            <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}><circle cx="8" cy="8" r="2" /></svg>
                          ) : (
                            <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}><path d="M4 4l8 8M12 4l-8 8" /></svg>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => { setConfirmDeleteId(null); }}
                          style={iconBtn(false)}
                          title="Cancel"
                        >
                          <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                            <path d="M4 8h8" />
                          </svg>
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        disabled={saving || isDiscovering}
                        title={`Delete ${sourceTitle(source)}`}
                        aria-label={`Delete ${sourceTitle(source)}`}
                        onClick={() => { setConfirmDeleteId(source.id); }}
                        style={{ ...iconBtn(false), color: "#9b3a2d", opacity: isDiscovering ? 0.4 : 1 }}
                      >
                        <svg fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 16 16" style={{ width: "15px", height: "15px" }}>
                          <path d="M3 5h10M6 5V3h4v2M6 8v5M10 8v5M4 5l1 8h6l1-8" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>

                {/* Row 2: status strip */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center", marginBottom: "8px" }}>
                  <StatusBadge status={source.status} />

                  {!isDiscovering && (
                    <>
                      <span style={{ color: theme.color.muted, fontSize: "12px" }}>
                        {source.post_count === 0
                          ? "0 posts"
                          : `${source.post_count} post${source.post_count === 1 ? "" : "s"}`}
                      </span>
                      <span style={{ color: theme.color.muted, fontSize: "12px" }}>·</span>
                      <span style={{ color: theme.color.muted, fontSize: "12px" }}>
                        Synced: {timeAgo(source.last_success_at)}
                      </span>
                      {source.last_failure_at && (
                        <>
                          <span style={{ color: theme.color.muted, fontSize: "12px" }}>·</span>
                          <span style={{ color: "#c47060", fontSize: "12px" }}>
                            Failed: {timeAgo(source.last_failure_at)}
                          </span>
                        </>
                      )}
                    </>
                  )}
                </div>

                {/* Sync hint */}
                {syncNeeded && (
                  <p style={{ background: "#eef4f9", borderRadius: "3px", color: "#2f5878", fontSize: "12px", margin: "0 0 8px", padding: "6px 10px" }}>
                    Feed discovered — click <strong>Sync sources now</strong> to fetch posts.
                  </p>
                )}

                {/* Row 3: technical details */}
                <div style={{ borderTop: `1px solid ${theme.color.border}`, display: "flex", flexWrap: "wrap", gap: "0 20px", marginTop: "8px", paddingTop: "8px" }}>
                  {source.strategy_kind && (
                    <span style={{ color: theme.color.muted, fontSize: "11px" }}>
                      <span style={{ fontFamily: theme.font.sectionTitle, letterSpacing: "0.08em", textTransform: "uppercase" }}>Strategy</span>{" "}
                      {source.strategy_kind}
                    </span>
                  )}
                  {source.feed_url && (
                    <span style={{ color: theme.color.muted, fontSize: "11px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "420px" }}>
                      <span style={{ fontFamily: theme.font.sectionTitle, letterSpacing: "0.08em", textTransform: "uppercase" }}>Feed</span>{" "}
                      <a href={source.feed_url} target="_blank" rel="noreferrer" style={{ color: theme.color.accent, textDecoration: "none" }}>{source.feed_url}</a>
                    </span>
                  )}
                </div>

                {/* Readaptation warning */}
                {source.needs_readaptation && (
                  <div style={{ background: "#fdf3e3", borderRadius: "3px", marginTop: "10px", padding: "8px 12px" }}>
                    <strong style={{ color: "#7a5c2a", fontSize: "12px" }}>Needs attention:</strong>
                    <span style={{ color: "#7a5c2a", fontSize: "12px", marginLeft: "6px" }}>{source.readaptation_reason ?? "No reason recorded."}</span>
                  </div>
                )}

                {/* Inline log terminal — shown when this source's log is active */}
                {activeLog?.sourceId === source.id && (
                  <div style={{ marginTop: "12px" }}>
                    <div style={{ backgroundColor: "#111b27", border: "1px solid #1e3048", borderRadius: theme.radius.card, overflow: "hidden" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 14px", borderBottom: "1px solid #1e3048", backgroundColor: "#0d1520" }}>
                        <span style={{ color: "#4a7095", fontFamily: theme.font.sectionTitle, fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase" }}>
                          Source log
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          {activeLog.done && activeLog.finalStatus ? (
                            <span style={{ color: logStatusColor(activeLog.finalStatus), fontFamily: theme.font.sectionTitle, fontSize: "11px", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                              {activeLog.finalStatus.replace(/_/g, " ")}
                            </span>
                          ) : (
                            <span style={{ color: "#4a7095", fontSize: "12px" }}>running…</span>
                          )}
                          <button type="button" onClick={() => { setActiveLog(null); }} style={{ background: "none", border: "none", color: "#4a7095", cursor: "pointer", fontSize: "16px", lineHeight: 1, padding: "0 2px" }} aria-label="Close log">×</button>
                        </div>
                      </div>
                      <div ref={terminalRef} style={{ color: "#c8dced", fontFamily: "'Consolas','Menlo','Monaco',monospace", fontSize: "12px", lineHeight: 1.6, maxHeight: "240px", overflowY: "auto", padding: "12px 16px" }}>
                        {activeLog.lines.length === 0 && !activeLog.done
                          ? <span style={{ color: "#4a7095" }}>Waiting for response…</span>
                          : activeLog.lines.map((line, i) => (
                            <div key={i}>
                              <span style={{ color: "#2f5878", userSelect: "none" }}>{formatLogTime(line.ts)}</span>
                              {" "}
                              <span style={{
                                color: line.msg.startsWith("  ") || line.msg.startsWith("─") ? "#4a6d8c"
                                  : /error|fail/i.test(line.msg) ? "#c47060"
                                  : /found|done|complete|ready|strategy:/i.test(line.msg) ? "#7fbf8e"
                                  : "#c8dced"
                              }}>
                                {line.msg}
                              </span>
                            </div>
                          ))}
                        {!activeLog.done && activeLog.lines.length > 0 && <div style={{ color: "#2f5878" }}>▌</div>}
                      </div>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
