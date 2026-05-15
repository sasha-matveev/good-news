import { useEffect, useState } from "react";

import { theme } from "../styles/theme";

import { SourceForm } from "../components/SourceForm";
import {
  createSource,
  listSources,
  runSourceSyncOnce,
  SourceRecord,
  updateSourceActive
} from "../lib/api";

function sourceTitle(source: SourceRecord) {
  return source.display_name ?? source.original_url;
}

function formatSourceDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

function formatStatus(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function SourceField({ label, value, href }: { label: string; value: string; href?: string }) {
  return (
    <>
      <span style={{ color: theme.color.muted, fontFamily: theme.font.sectionTitle, fontSize: "11px", letterSpacing: "0.1em", textTransform: "uppercase", paddingRight: "12px", alignSelf: "start" }}>
        {label}
      </span>
      <span style={{ fontSize: "13px", color: theme.color.text, wordBreak: "break-all" }}>
        {href
          ? <a href={href} target="_blank" rel="noreferrer" style={{ color: theme.color.accent, textDecoration: "none" }}>{value}</a>
          : value}
      </span>
    </>
  );
}

type PendingAction =
  | { type: "add" }
  | { type: "sync" }
  | { type: "toggle"; sourceId: number }
  | null;

export function SourcesPage() {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const saving = pendingAction !== null;

  async function reloadSources() {
    const nextSources = await listSources();
    setSources(nextSources);
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const nextSources = await listSources();
        if (!cancelled) {
          setSources(nextSources);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load sources.");
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

  async function handleAddSource(url: string) {
    setPendingAction({ type: "add" });
    try {
      const created = await createSource(url);
      setSources((current) => [...current, created]);
      setError(null);
      setSyncStatus(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to add source.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleToggle(source: SourceRecord) {
    setPendingAction({ type: "toggle", sourceId: source.id });
    try {
      const updated = await updateSourceActive(source.id, !source.active);
      setSources((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry))
      );
      setError(null);
      setSyncStatus(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update source.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSync() {
    setPendingAction({ type: "sync" });
    try {
      const result = await runSourceSyncOnce();
      await reloadSources();
      const processedCount = result.processed_source_ids.length;
      setSyncStatus(
        processedCount === 0
          ? "Sync complete. No active sources were processed."
          : `Sync complete for ${processedCount} source${processedCount === 1 ? "" : "s"}.`
      );
      setError(null);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "Failed to sync sources.");
      setSyncStatus(null);
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <section style={{ padding: "32px 24px 40px" }}>
      <div style={{ marginBottom: "24px" }}>
        <p
          style={{
            fontFamily: theme.font.sectionTitle,
            fontSize: "12px",
            letterSpacing: "0.16em",
            margin: 0,
            textTransform: "uppercase"
          }}
        >
          Sources
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Manage your content sources
        </h2>
      </div>

      <SourceForm
        disabled={saving}
        onSubmit={handleAddSource}
        submitLabel={pendingAction?.type === "add" ? "Adding source..." : "Add source"}
      />

      <div style={{ marginBottom: "24px" }}>
        <button
          type="button"
          disabled={saving || loading || sources.length === 0}
          onClick={() => {
            void handleSync();
          }}
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

      {error ? (
        <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
          {error}
        </p>
      ) : null}

      {syncStatus ? <p>{syncStatus}</p> : null}

      {loading ? (
        <p>Loading sources…</p>
      ) : sources.length === 0 ? (
        <p>No sources yet.</p>
      ) : (
        <div style={{ display: "grid", gap: "16px" }}>
          {sources.map((source) => (
            <article
              key={source.id}
              style={{
                backgroundColor: theme.color.card,
                border: `1px solid ${theme.color.border}`,
                borderRadius: theme.radius.card,
                padding: "18px 20px"
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: "16px",
                  alignItems: "flex-start"
                }}
              >
                <div>
                  <h3 style={{ fontSize: "20px", margin: "0 0 4px" }}>
                    {sourceTitle(source)}
                  </h3>
                  <a
                    href={source.original_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: theme.color.muted, fontSize: "12px", wordBreak: "break-all", textDecoration: "none" }}
                  >
                    {source.original_url}
                  </a>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 0", marginTop: "8px" }}>
                    <SourceField label="Status" value={formatStatus(source.status)} />
                    <SourceField label="Strategy" value={source.strategy_kind ?? "unknown"} />
                    {source.feed_url ? <SourceField label="Feed URL" value={source.feed_url} href={source.feed_url} /> : null}
                    <SourceField label="Last success" value={formatSourceDate(source.last_success_at)} />
                    <SourceField label="Last failure" value={formatSourceDate(source.last_failure_at)} />
                  </div>
                  {source.needs_readaptation ? (
                    <div style={{ marginTop: "12px" }}>
                      <strong>Needs readaptation</strong>
                      <p style={{ margin: "8px 0 0" }}>
                        {source.readaptation_reason ?? "No reason recorded."}
                      </p>
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    void handleToggle(source);
                  }}
                  style={{
                    backgroundColor: source.active ? theme.color.border : theme.color.accent,
                    border: source.active ? `1px solid ${theme.color.border}` : `1px solid ${theme.color.accent}`,
                    borderRadius: theme.radius.card,
                    color: source.active ? theme.color.text : "#ffffff",
                    fontFamily: "inherit",
                    padding: "10px 14px"
                  }}
                >
                  {pendingAction?.type === "toggle" && pendingAction.sourceId === source.id
                    ? "Updating..."
                    : source.active
                      ? `Disable ${sourceTitle(source)}`
                      : `Enable ${sourceTitle(source)}`}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
