import { useEffect, useState } from "react";

import { PreferenceSummary } from "../components/PreferenceSummary";
import { getPreferenceProfile, recomputePreferenceProfile, type PreferenceProfileRecord } from "../lib/api";
import { theme } from "../styles/theme";

export function PreferenceProfilePage() {
  const [profile, setProfile] = useState<PreferenceProfileRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const nextProfile = await getPreferenceProfile();
        if (!cancelled) {
          setProfile(nextProfile);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load preference profile.");
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

  async function handleRebuild() {
    setRebuilding(true);
    setError(null);
    try {
      const nextProfile = await recomputePreferenceProfile();
      setProfile(nextProfile);
    } catch (rebuildError) {
      setError(rebuildError instanceof Error ? rebuildError.message : "Failed to rebuild preference profile.");
    } finally {
      setRebuilding(false);
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
          Preference Profile
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Why the ranking engine leans the way it does
        </h2>
        <button
          type="button"
          disabled={rebuilding || loading}
          onClick={() => { void handleRebuild(); }}
          style={{
            backgroundColor: theme.color.accent,
            border: `1px solid ${theme.color.accent}`,
            borderRadius: theme.radius.card,
            color: "#ffffff",
            cursor: rebuilding || loading ? "default" : "pointer",
            fontFamily: "inherit",
            fontSize: "13px",
            marginTop: "16px",
            padding: "9px 16px"
          }}
        >
          {rebuilding ? "Rebuilding…" : "Rebuild from reactions"}
        </button>
        <p style={{ color: theme.color.muted, fontSize: "12px", margin: "8px 0 0", lineHeight: 1.4, maxWidth: "560px" }}>
          The profile only learns from posts that have both a reaction and a completed analysis.
          If signals look stale, drain the LLM queue on the Monitoring tab first.
        </p>
      </div>

      {error ? (
        <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
          {error}
        </p>
      ) : null}

      {loading ? (
        <p>Loading preference profile...</p>
      ) : profile ? (
        <PreferenceSummary profile={profile} />
      ) : (
        <p>No preference profile yet.</p>
      )}
    </section>
  );
}
