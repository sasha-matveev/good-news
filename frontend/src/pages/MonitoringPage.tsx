import { useEffect, useState } from "react";

import { fetchMonitoringSummary, MonitoringSummary, ServiceHealth } from "../lib/api";
import { useSetMonitoringSummary } from "../lib/MonitoringContext";
import { theme } from "../styles/theme";

const GRAFANA_URL =
  "http://127.0.0.1:3000/d/good-news-overview/good-news-observability-overview";

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

export function MonitoringPage() {
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const setContextSummary = useSetMonitoringSummary();

  useEffect(() => {
    fetchMonitoringSummary().then((data) => {
      setSummary(data);
      setContextSummary(data);
    });
  }, [setContextSummary]);

  const svc = summary?.services;

  return (
    <section style={{ padding: "24px" }}>
      <div style={{ alignItems: "center", display: "flex", justifyContent: "space-between", marginBottom: "24px" }}>
        <h2 style={{ fontFamily: theme.font.sectionTitle, margin: 0 }}>Monitoring</h2>
        <a
          href={GRAFANA_URL}
          rel="noopener noreferrer"
          style={{
            background: theme.color.accent,
            borderRadius: theme.radius.card,
            color: theme.color.card,
            fontFamily: theme.font.body,
            fontSize: "14px",
            padding: "8px 16px",
            textDecoration: "none"
          }}
          target="_blank"
        >
          Open Grafana
        </a>
      </div>

      <div style={{ display: "grid", gap: "16px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>

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
        </article>

        <article style={{ background: theme.color.card, border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.card, padding: "20px" }}>
          <h3 style={{ fontFamily: theme.font.sectionTitle, margin: "0 0 12px" }}>Capacity</h3>
          <MetricRow label="Posts collected" value={summary !== null ? String(summary.posts_total) : "—"} />
          <MetricRow label="Last sync" value={formatLastSync(summary?.last_sync_at ?? null)} />
        </article>

      </div>
    </section>
  );
}
