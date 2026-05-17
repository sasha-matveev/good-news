import { useEffect, useState } from "react";

import { PreferenceSummary } from "../components/PreferenceSummary";
import { getPreferenceProfile, type PreferenceProfileRecord } from "../lib/api";
import { theme } from "../styles/theme";

export function PreferenceProfilePage() {
  const [profile, setProfile] = useState<PreferenceProfileRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
