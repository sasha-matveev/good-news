import { useEffect, useState } from "react";

import { DigestsPage } from "../pages/DigestsPage";
import { FeedPage } from "../pages/FeedPage";
import { MonitoringPage } from "../pages/MonitoringPage";
import { PreferenceProfilePage } from "../pages/PreferenceProfilePage";
import { SettingsPage } from "../pages/SettingsPage";
import { SourcesPage } from "../pages/SourcesPage";
import { WantToReadPage } from "../pages/WantToReadPage";
import { MonitoringContext } from "../lib/MonitoringContext";
import { fetchMonitoringSummary, type MonitoringSummary } from "../lib/api";
import { theme } from "../styles/theme";

const tabs = [
  "Feed",
  "Want To Read",
  "Preference Profile",
  "Sources",
  "Digests",
  "Settings",
  "Monitoring"
] as const;

const tabPaths: Record<(typeof tabs)[number], string> = {
  Feed: "/feed",
  "Want To Read": "/want-to-read",
  "Preference Profile": "/preference-profile",
  Sources: "/sources",
  Digests: "/digests",
  Settings: "/settings",
  Monitoring: "/monitoring"
};

function tabFromPath(pathname: string): (typeof tabs)[number] {
  const normalizedPath = pathname.trim().toLowerCase();
  return (
    (Object.entries(tabPaths).find(([, path]) => path === normalizedPath)?.[0] as
      | (typeof tabs)[number]
      | undefined) ?? "Feed"
  );
}

export function AppShell() {
  const search = new URLSearchParams(window.location.search);
  const initialDigestIdValue = search.get("digest_id");
  const initialDigestId =
    initialDigestIdValue && /^[0-9]+$/.test(initialDigestIdValue)
      ? Number(initialDigestIdValue)
      : null;
  const initialPostIdValue = search.get("post_id");
  const initialPostId =
    initialPostIdValue && /^[0-9]+$/.test(initialPostIdValue)
      ? Number(initialPostIdValue)
      : null;
  const initialFeedbackState = search.get("feedback");
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>(() =>
    tabFromPath(window.location.pathname)
  );
  const [monitoringSummary, setMonitoringSummary] = useState<MonitoringSummary | null>(null);

  useEffect(() => {
    fetchMonitoringSummary().then((data) => {
      if (data) setMonitoringSummary(data);
    });
  }, []);

  function activateTab(tab: (typeof tabs)[number]) {
    setActiveTab(tab);
    window.history.replaceState({}, "", tabPaths[tab]);
  }

  return (
    <MonitoringContext.Provider value={{ summary: monitoringSummary, setSummary: setMonitoringSummary }}>
    <main
      style={{
        minHeight: "100vh",
        background: `linear-gradient(180deg, ${theme.color.pageTop} 0%, ${theme.color.pageBottom} 100%)`,
        color: theme.color.text,
        fontFamily: theme.font.body,
        padding: "24px 20px"
      }}
    >
      <section
        style={{
          margin: "0 auto",
          maxWidth: "1200px",
          backgroundColor: theme.color.shell,
          border: `1px solid ${theme.color.border}`,
          borderRadius: theme.radius.shell,
          boxShadow: "0 18px 40px rgba(25, 34, 43, 0.12)",
          overflow: "hidden"
        }}
      >
        <header
          style={{
            borderBottom: `1px solid ${theme.color.border}`,
            padding: "20px 24px"
          }}
        >
          <div
            style={{
              alignItems: "start",
              display: "grid",
              gap: "16px",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))"
            }}
          >
            <article
              style={{
                backgroundColor: theme.color.card,
                border: `1px solid ${theme.color.border}`,
                borderRadius: theme.radius.card,
                padding: "16px"
              }}
            >
              <p
                style={{
                  color: theme.color.muted,
                  fontFamily: theme.font.sectionTitle,
                  fontSize: "12px",
                  letterSpacing: "0.12em",
                  margin: 0,
                  textTransform: "uppercase"
                }}
              >
                Tracked sources
              </p>
              <h1
                style={{
                  fontFamily: theme.font.sectionTitle,
                  fontSize: "28px",
                  margin: "10px 0 0"
                }}
              >
                {monitoringSummary ? `${monitoringSummary.sources_active}/${monitoringSummary.sources_total}` : "—"}
              </h1>
              <p style={{ color: theme.color.muted, margin: "8px 0 0" }}>
                {monitoringSummary
                  ? `${monitoringSummary.sources_active} active of ${monitoringSummary.sources_total} tracked`
                  : "Active sources"}
              </p>
            </article>
            <article
              style={{
                backgroundColor: theme.color.card,
                border: `1px solid ${theme.color.border}`,
                borderRadius: theme.radius.card,
                padding: "16px"
              }}
            >
              <p
                style={{
                  color: theme.color.muted,
                  fontFamily: theme.font.sectionTitle,
                  fontSize: "12px",
                  letterSpacing: "0.12em",
                  margin: 0,
                  textTransform: "uppercase"
                }}
              >
                System
              </p>
              <p style={{ margin: "10px 0 0" }}>
                {monitoringSummary ? "Online" : "Status unavailable"}
              </p>
            </article>
            <article
              style={{
                backgroundColor: theme.color.card,
                border: `1px solid ${theme.color.border}`,
                borderRadius: theme.radius.card,
                padding: "16px"
              }}
            >
              <p
                style={{
                  color: theme.color.muted,
                  fontFamily: theme.font.sectionTitle,
                  fontSize: "12px",
                  letterSpacing: "0.12em",
                  margin: 0,
                  textTransform: "uppercase"
                }}
              >
                Capacity
              </p>
              <p style={{ margin: "10px 0 0" }}>
                {monitoringSummary
                  ? monitoringSummary.last_sync_at
                    ? `Last sync: ${monitoringSummary.last_sync_at.replace("T", " ").slice(0, 16)}` /* "YYYY-MM-DD HH:MM" */
                    : "No syncs yet"
                  : "—"}
              </p>
            </article>
          </div>
        </header>

        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "600px" }}>
          <nav
            aria-label="Primary navigation"
            style={{
              backgroundColor: "#edf3f8",
              borderRight: `1px solid ${theme.color.border}`,
              padding: "16px",
              display: "grid",
              alignContent: "start",
              gap: "4px"
            }}
          >
            <p
              style={{
                color: theme.color.muted,
                fontFamily: theme.font.sectionTitle,
                fontSize: "11px",
                fontWeight: 700,
                letterSpacing: "0.2em",
                margin: "0 0 10px",
                textTransform: "uppercase"
              }}
            >
              Sections
            </p>
            {tabs.map((tab) => (
              <button
                key={tab}
                aria-current={activeTab === tab ? "page" : undefined}
                onClick={() => { activateTab(tab); }}
                style={{
                  backgroundColor: activeTab === tab ? theme.color.accent : "transparent",
                  border: `1px solid ${activeTab === tab ? theme.color.accent : "transparent"}`,
                  borderRadius: theme.radius.card,
                  color: activeTab === tab ? theme.color.card : theme.color.text,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontSize: "15px",
                  padding: "11px 12px",
                  textAlign: "left",
                  width: "100%"
                }}
                type="button"
              >
                {tab}
              </button>
            ))}
          </nav>
          <div>
            {activeTab === "Feed" ? (
              <FeedPage />
            ) : activeTab === "Want To Read" ? (
              <WantToReadPage feedbackState={initialFeedbackState} postId={initialPostId} />
            ) : activeTab === "Preference Profile" ? (
              <PreferenceProfilePage />
            ) : activeTab === "Sources" ? (
              <SourcesPage />
            ) : activeTab === "Digests" ? (
              <DigestsPage
                feedbackState={initialFeedbackState}
                initialDigestId={initialDigestId}
                postId={initialPostId}
              />
            ) : activeTab === "Settings" ? (
              <SettingsPage />
            ) : activeTab === "Monitoring" ? (
              <MonitoringPage />
            ) : null}
          </div>
        </div>
      </section>
    </main>
    </MonitoringContext.Provider>
  );
}
