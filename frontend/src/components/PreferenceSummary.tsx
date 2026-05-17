import { theme } from "../styles/theme";
import type { PreferenceProfileRecord } from "../lib/api";

type PreferenceSummaryProps = {
  profile: PreferenceProfileRecord;
};

export function PreferenceSummary({ profile }: PreferenceSummaryProps) {
  return (
    <section style={{ display: "grid", gap: "18px" }}>
      <p style={{ fontSize: "20px", lineHeight: 1.6, margin: 0 }}>{profile.summary}</p>

      <article
        style={{
          background: theme.color.shell,
          border: `1px solid ${theme.color.border}`,
          borderRadius: theme.radius.shell,
          padding: "18px 20px"
        }}
      >
        <h3 style={{ marginTop: 0 }}>Learning proof</h3>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "10px",
            marginBottom: "14px"
          }}
        >
          <span
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              padding: "6px 10px"
            }}
          >
            Total feedback: {profile.feedback_totals.total}
          </span>
          <span
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              padding: "6px 10px"
            }}
          >
            Interesting: {profile.feedback_totals.interesting}
          </span>
          <span
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              padding: "6px 10px"
            }}
          >
            Want to read: {profile.feedback_totals.want_to_read}
          </span>
          <span
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              padding: "6px 10px"
            }}
          >
            Not interesting: {profile.feedback_totals.not_interesting}
          </span>
        </div>
        <ul style={{ margin: 0, paddingLeft: "20px" }}>
          {profile.learning_proof.map((signal) => (
            <li key={signal}>{signal}</li>
          ))}
        </ul>
      </article>

      <div
        style={{
          display: "grid",
          gap: "16px",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))"
        }}
      >
        <article
          style={{
            backgroundColor: theme.color.shell,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.shell,
            padding: "18px 20px"
          }}
        >
          <h3 style={{ marginTop: 0 }}>Positive signals</h3>
          {profile.positive_signals.length === 0 ? (
            <p style={{ margin: 0 }}>No positive signals recorded yet.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: "20px" }}>
              {profile.positive_signals.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          )}
        </article>

        <article
          style={{
            backgroundColor: theme.color.shell,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.shell,
            padding: "18px 20px"
          }}
        >
          <h3 style={{ marginTop: 0 }}>Negative signals</h3>
          {profile.negative_signals.length === 0 ? (
            <p style={{ margin: 0 }}>No strong negative tendencies yet.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: "20px" }}>
              {profile.negative_signals.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  );
}
