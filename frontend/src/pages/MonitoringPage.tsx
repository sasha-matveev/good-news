import { useEffect, useState } from "react";

import { analyzePendingNow, fetchMonitoringSummary, getAnalysisQueue, MonitoringSummary, QueueItem, ServiceHealth } from "../lib/api";
import { useSetMonitoringSummary } from "../lib/MonitoringContext";
import { theme } from "../styles/theme";

function formatLastSync(lastSyncAt: string | null): string {
  if (!lastSyncAt) return "—";
  return lastSyncAt.split("T")[0] ?? lastSyncAt;
}

function StatusDot({ status }: { status: ServiceHealth | undefined }) {
  const ok = status === "ok";
  return (
    <span style={{
      display: "inline-block",
      width: "8px",
      height: "8px",
      borderRadius: "50%",
      backgroundColor: ok ? "#4a7c59" : (status === undefined ? theme.color.border : "#9b3a2d"),
      marginRight: "6px",
      flexShrink: 0
    }} />
  );
}

type MetricRowProps = { label: string; value: string };
function MetricRow({ label, value }: MetricRowProps) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", padding: "6px 0", borderBottom: `1px solid ${theme.color.border}` }}>
      <span style={{ color: theme.color.muted, fontFamily: theme.font.sectionTitle, fontSize: "12px", letterSpacing: "0.1em", textTransform: "uppercase" }}>
        {label}
      </span>
      <span style={{ fontWeight: 600, fontSize: "15px" }}>{value}</span>
    </div>
  );
}

type ServiceRowProps = { label: string; status: ServiceHealth | undefined };
function ServiceRow({ label, status }: ServiceRowProps) {
  const text = status === "ok" ? "OK" : status === "error" ? "Error" : "—";
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "6px 0", borderBottom: `1px solid ${theme.color.border}` }}>
      <StatusDot status={status} />
      <span style={{ flex: 1, fontFamily: theme.font.sectionTitle, fontSize: "12px", letterSpacing: "0.1em", textTransform: "uppercase", color: theme.color.muted }}>
        {label}
      </span>
      <span style={{ fontWeight: 600, fontSize: "15px" }}>{text}</span>
    </div>
  );
}

function formatQueueDate(value: string | null): string {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

export function MonitoringPage() {
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const [queue, setQueue] = useState<QueueItem[] | null>(null);
  const [queueExpanded, setQueueExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeMsg, setAnalyzeMsg] = useState<string | null>(null);
  const setContextSummary = useSetMonitoringSummary();

  async function refresh() {
    const [summaryData, queueData] = await Promise.all([
      fetchMonitoringSummary(),
      getAnalysisQueue().catch(() => [] as QueueItem[]),
    ]);
    setSummary(summaryData);
    setContextSummary(summaryData);
    setQueue(queueData);
    setLoading(false);
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [summaryData, queueData] = await Promise.all([
        fetchMonitoringSummary(),
        getAnalysisQueue().catch(() => [] as QueueItem[]),
      ]);
      if (cancelled) return;
      setSummary(summaryData);
      setContextSummary(summaryData);
      setQueue(queueData);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [setContextSummary]);

  async function handleAnalyzeNow() {
    setAnalyzing(true);
    setAnalyzeMsg(null);
    try {
      const result = await analyzePendingNow();
      setAnalyzeMsg(
        result.remaining > 0
          ? `Analyzed ${result.analyzed}. ${result.remaining} still pending — click again to continue.`
          : `Analyzed ${result.analyzed}. Queue empty.`
      );
      await refresh();
    } catch {
      setAnalyzeMsg("Analysis run failed. Try again in a moment.");
    } finally {
      setAnalyzing(false);
    }
  }

  const svc = summary?.services;
  const pending = summary?.posts_unranked ?? 0;

  return (
    <section style={{ padding: "24px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h2 style={{ fontFamily: theme.font.sectionTitle, margin: 0 }}>Monitoring</h2>
        {loading ? (
          <p style={{ color: theme.color.muted, fontSize: "13px", margin: "8px 0 0" }}>
            Loading…
          </p>
        ) : null}
      </div>

      <div style={{ display: "grid", gap: "16px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", opacity: loading ? 0.5 : 1 }}>

        <article style={{ background: theme.color.card, border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.card, padding: "20px" }}>
          <h3 style={{ fontFamily: theme.font.sectionTitle, margin: "0 0 12px" }}>Source health</h3>
          <MetricRow label="Active" value={summary !== null ? String(summary.sources_active) : "—"} />
          <MetricRow label="Total" value={summary !== null ? String(summary.sources_total) : "—"} />
          <MetricRow label="Last sync" value={formatLastSync(summary?.last_sync_at ?? null)} />
        </article>

        <article style={{ background: theme.color.card, border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.card, padding: "20px" }}>
          <h3 style={{ fontFamily: theme.font.sectionTitle, margin: "0 0 12px" }}>System health</h3>
          <ServiceRow label="Content API" status={svc?.content_api} />
          <ServiceRow label="Analysis LLM" status={svc?.analysis_llm} />
          <ServiceRow label="Source ingest" status={svc?.source_ingestion} />
          <ServiceRow label="Delivery" status={svc?.delivery} />
        </article>

        <article style={{ background: theme.color.card, border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.card, padding: "20px" }}>
          <h3 style={{ fontFamily: theme.font.sectionTitle, margin: "0 0 12px" }}>LLM queue</h3>
          <MetricRow label="Pending ranking" value={summary !== null ? String(summary.posts_unranked) : "—"} />
          <MetricRow label="Total posts" value={summary !== null ? String(summary.posts_total) : "—"} />

          <button
            type="button"
            disabled={analyzing || loading || pending === 0}
            onClick={() => { void handleAnalyzeNow(); }}
            style={{
              backgroundColor: pending === 0 ? theme.color.border : theme.color.llm,
              border: `1px solid ${pending === 0 ? theme.color.border : theme.color.llm}`,
              borderRadius: theme.radius.card,
              color: "#ffffff",
              cursor: analyzing || pending === 0 ? "default" : "pointer",
              fontFamily: "inherit",
              fontSize: "13px",
              marginTop: "12px",
              padding: "9px 14px",
              width: "100%"
            }}
          >
            {analyzing ? "Analyzing…" : "Analyze pending now"}
          </button>
          {analyzeMsg ? (
            <p style={{ color: theme.color.muted, fontSize: "12px", margin: "8px 0 0", lineHeight: 1.4 }}>
              {analyzeMsg}
            </p>
          ) : null}
          {queue !== null && queue.length > 0 ? (
            <div style={{ marginTop: "12px" }}>
              <button
                type="button"
                onClick={() => { setQueueExpanded((v) => !v); }}
                style={{
                  background: "none",
                  border: "none",
                  color: theme.color.accent,
                  cursor: "pointer",
                  fontFamily: theme.font.sectionTitle,
                  fontSize: "11px",
                  letterSpacing: "0.1em",
                  padding: 0,
                  textTransform: "uppercase"
                }}
              >
                {queueExpanded ? "▲ Hide queue" : `▼ Show ${queue.length} pending post${queue.length === 1 ? "" : "s"}`}
              </button>
              {queueExpanded ? (
                <div style={{ marginTop: "10px", display: "grid", gap: "6px" }}>
                  {queue.map((item) => (
                    <div
                      key={item.post_id}
                      style={{
                        backgroundColor: theme.color.border,
                        borderRadius: "3px",
                        fontSize: "12px",
                        padding: "7px 10px"
                      }}
                    >
                      <div style={{ color: theme.color.text, fontWeight: 600, marginBottom: "2px", lineHeight: 1.3 }}>
                        {item.title}
                      </div>
                      <div style={{ color: theme.color.muted, display: "flex", gap: "12px" }}>
                        <span>{item.source_name ?? "unknown source"}</span>
                        <span>{formatQueueDate(item.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : queue !== null && queue.length === 0 ? (
            <div style={{ color: "#4a7c59", fontFamily: theme.font.sectionTitle, fontSize: "11px", letterSpacing: "0.1em", marginTop: "10px", textTransform: "uppercase" }}>
              Queue empty
            </div>
          ) : null}
        </article>


      </div>
    </section>
  );
}
