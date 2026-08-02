import { FormEvent, useEffect, useState } from "react";

import { MarkdownEditor } from "../components/MarkdownEditor";
import { theme } from "../styles/theme";
import {
  getSettings,
  sendTestEmail,
  type SettingsRecord,
  type WeeklyDigestDayOfWeek,
  updateSettings
} from "../lib/api";

type SettingsFormState = {
  daily_digest_time: string;
  weekly_digest_day_of_week: WeeklyDigestDayOfWeek;
  weekly_digest_time: string;
  recipient_email: string;
  sender_identity: string;
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_security_mode: "none" | "starttls" | "ssl";
  daily_digest_enabled: boolean;
  daily_digest_catch_up_enabled: boolean;
  weekly_digest_enabled: boolean;
  weekly_digest_catch_up_enabled: boolean;
  replace_password: boolean;
  smtp_password: string;
  analysis_summary_prompt: string;
  analysis_verdict_reason_prompt: string;
};

const WEEKDAY_OPTIONS: Array<{ label: string; value: WeeklyDigestDayOfWeek }> = [
  { label: "Monday", value: "mon" },
  { label: "Tuesday", value: "tue" },
  { label: "Wednesday", value: "wed" },
  { label: "Thursday", value: "thu" },
  { label: "Friday", value: "fri" },
  { label: "Saturday", value: "sat" },
  { label: "Sunday", value: "sun" }
];

function buildFormState(settings: SettingsRecord): SettingsFormState {
  return {
    daily_digest_time: settings.daily_digest_time,
    weekly_digest_day_of_week: settings.weekly_digest_day_of_week,
    weekly_digest_time: settings.weekly_digest_time,
    recipient_email: settings.recipient_email ?? "",
    sender_identity: settings.sender_identity ?? "",
    smtp_host: settings.smtp_host ?? "",
    smtp_port: String(settings.smtp_port),
    smtp_username: settings.smtp_username ?? "",
    smtp_security_mode: settings.smtp_security_mode,
    daily_digest_enabled: settings.daily_digest_enabled,
    daily_digest_catch_up_enabled: settings.daily_digest_catch_up_enabled,
    weekly_digest_enabled: settings.weekly_digest_enabled,
    weekly_digest_catch_up_enabled: settings.weekly_digest_catch_up_enabled,
    replace_password: false,
    smtp_password: "",
    analysis_summary_prompt: settings.analysis_summary_prompt,
    analysis_verdict_reason_prompt: settings.analysis_verdict_reason_prompt
  };
}

export function SettingsPage() {
  const [form, setForm] = useState<SettingsFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [passwordConfigured, setPasswordConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const settings = await getSettings();
        if (!cancelled) {
          setForm(buildFormState(settings));
          setPasswordConfigured(settings.smtp_password_configured);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load settings.");
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) {
      return;
    }

    setSaving(true);
    setSuccessMessage(null);
    try {
      const updated = await updateSettings({
        daily_digest_time: form.daily_digest_time,
        weekly_digest_day_of_week: form.weekly_digest_day_of_week,
        weekly_digest_time: form.weekly_digest_time,
        recipient_email: form.recipient_email || null,
        sender_identity: form.sender_identity || null,
        smtp_host: form.smtp_host || null,
        smtp_port: Number.parseInt(form.smtp_port, 10),
        smtp_username: form.smtp_username || null,
        smtp_security_mode: form.smtp_security_mode,
        daily_digest_enabled: form.daily_digest_enabled,
        daily_digest_catch_up_enabled: form.daily_digest_catch_up_enabled,
        weekly_digest_enabled: form.weekly_digest_enabled,
        weekly_digest_catch_up_enabled: form.weekly_digest_catch_up_enabled,
        analysis_summary_prompt: form.analysis_summary_prompt,
        analysis_verdict_reason_prompt: form.analysis_verdict_reason_prompt,
        ...(form.replace_password ? { smtp_password: form.smtp_password } : {})
      });
      setForm(buildFormState(updated));
      setPasswordConfigured(updated.smtp_password_configured);
      setSuccessMessage("Settings saved.");
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTestEmail() {
    setTestingEmail(true);
    setSuccessMessage(null);
    try {
      await sendTestEmail();
      setSuccessMessage("Test email sent.");
      setError(null);
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "Failed to send test email.");
    } finally {
      setTestingEmail(false);
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
          Settings
        </p>
        <h2 style={{ fontSize: "28px", margin: "14px 0 0" }}>
          Digest schedules and SMTP delivery
        </h2>
      </div>

      {error ? (
        <p role="alert" style={{ color: "#7f2f1d", marginTop: 0 }}>
          {error}
        </p>
      ) : null}
      {successMessage ? <p>{successMessage}</p> : null}

      {loading || !form ? (
        <p>Loading settings...</p>
      ) : (
        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          style={{ display: "grid", gap: "14px", maxWidth: "640px" }}
        >
          <section
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              display: "grid",
              gap: "14px",
              padding: "18px"
            }}
          >
            <div>
              <h3 style={{ fontSize: "20px", margin: 0 }}>Daily digest</h3>
            </div>

            <label style={{ display: "grid", gap: "8px" }}>
              <span>Daily digest time</span>
              <input
                aria-label="Daily digest time"
                type="time"
                value={form.daily_digest_time}
                onChange={(event) => {
                  setForm((current) => current ? { ...current, daily_digest_time: event.target.value } : current);
                }}
              />
            </label>

            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                aria-label="Enable daily digest"
                type="checkbox"
                checked={form.daily_digest_enabled}
                onChange={(event) => {
                  setForm((current) => current ? { ...current, daily_digest_enabled: event.target.checked } : current);
                }}
              />
              <span>Enable daily digest</span>
            </label>

            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                aria-label="Disable startup catch-up"
                type="checkbox"
                checked={!form.daily_digest_catch_up_enabled}
                onChange={(event) => {
                  setForm((current) =>
                    current
                      ? { ...current, daily_digest_catch_up_enabled: !event.target.checked }
                      : current
                  );
                }}
              />
              <span>Disable startup catch-up</span>
            </label>
          </section>

          <section
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              display: "grid",
              gap: "14px",
              padding: "18px"
            }}
          >
            <div>
              <h3 style={{ fontSize: "20px", margin: 0 }}>Weekly digest</h3>
            </div>

            <label style={{ display: "grid", gap: "8px" }}>
              <span>Weekly digest day</span>
              <select
                aria-label="Weekly digest day of week"
                value={form.weekly_digest_day_of_week}
                onChange={(event) => {
                  setForm((current) =>
                    current
                      ? {
                          ...current,
                          weekly_digest_day_of_week: event.target.value as WeeklyDigestDayOfWeek
                        }
                      : current
                  );
                }}
              >
                {WEEKDAY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label style={{ display: "grid", gap: "8px" }}>
              <span>Weekly digest time</span>
              <input
                aria-label="Weekly digest time"
                type="time"
                value={form.weekly_digest_time}
                onChange={(event) => {
                  setForm((current) => current ? { ...current, weekly_digest_time: event.target.value } : current);
                }}
              />
            </label>

            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                aria-label="Enable weekly digest"
                type="checkbox"
                checked={form.weekly_digest_enabled}
                onChange={(event) => {
                  setForm((current) => current ? { ...current, weekly_digest_enabled: event.target.checked } : current);
                }}
              />
              <span>Enable weekly digest</span>
            </label>

            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                aria-label="Disable weekly startup catch-up"
                type="checkbox"
                checked={!form.weekly_digest_catch_up_enabled}
                onChange={(event) => {
                  setForm((current) =>
                    current
                      ? { ...current, weekly_digest_catch_up_enabled: !event.target.checked }
                      : current
                  );
                }}
              />
              <span>Disable weekly startup catch-up</span>
            </label>
          </section>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>Recipient email</span>
            <input
              aria-label="Recipient email"
              type="email"
              value={form.recipient_email}
              onChange={(event) => {
                setForm((current) => current ? { ...current, recipient_email: event.target.value } : current);
              }}
            />
          </label>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>Sender identity</span>
            <input
              aria-label="Sender identity"
              type="text"
              value={form.sender_identity}
              onChange={(event) => {
                setForm((current) => current ? { ...current, sender_identity: event.target.value } : current);
              }}
            />
          </label>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>SMTP host</span>
            <input
              aria-label="SMTP host"
              type="text"
              value={form.smtp_host}
              onChange={(event) => {
                setForm((current) => current ? { ...current, smtp_host: event.target.value } : current);
              }}
            />
          </label>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>SMTP port</span>
            <input
              aria-label="SMTP port"
              type="number"
              value={form.smtp_port}
              onChange={(event) => {
                setForm((current) => current ? { ...current, smtp_port: event.target.value } : current);
              }}
            />
          </label>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>SMTP username</span>
            <input
              aria-label="SMTP username"
              type="text"
              value={form.smtp_username}
              onChange={(event) => {
                setForm((current) => current ? { ...current, smtp_username: event.target.value } : current);
              }}
            />
          </label>

          <label style={{ display: "grid", gap: "8px" }}>
            <span>Security mode</span>
            <select
              aria-label="Security mode"
              value={form.smtp_security_mode}
              onChange={(event) => {
                setForm((current) =>
                  current
                    ? {
                        ...current,
                        smtp_security_mode: event.target.value as "none" | "starttls" | "ssl"
                      }
                    : current
                );
              }}
            >
              <option value="none">None</option>
              <option value="starttls">STARTTLS</option>
              <option value="ssl">SSL</option>
            </select>
          </label>

          <div>
            <p style={{ margin: "0 0 8px" }}>
              {passwordConfigured ? "SMTP password configured" : "SMTP password not configured"}
            </p>
            <label style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "8px" }}>
              <input
                aria-label="Replace SMTP password"
                type="checkbox"
                checked={form.replace_password}
                onChange={(event) => {
                  setForm((current) =>
                    current ? { ...current, replace_password: event.target.checked, smtp_password: "" } : current
                  );
                }}
              />
              <span>Replace SMTP password</span>
            </label>
            {form.replace_password ? (
              <input
                aria-label="New SMTP password"
                type="password"
                value={form.smtp_password}
                onChange={(event) => {
                  setForm((current) => current ? { ...current, smtp_password: event.target.value } : current);
                }}
              />
            ) : null}
          </div>

          <section
            style={{
              backgroundColor: theme.color.card,
              border: `1px solid ${theme.color.border}`,
              borderRadius: theme.radius.card,
              display: "grid",
              gap: "14px",
              padding: "18px"
            }}
          >
            <div>
              <h3 style={{ fontSize: "20px", margin: 0 }}>AI analysis</h3>
              <p style={{ color: theme.color.muted, fontSize: "13px", margin: "6px 0 0" }}>
                Only the content guidance below is editable. The JSON contract the model must follow
                (field names, allowed verdict/topics/format/depth values) is fixed in code so the
                analysis keeps parsing.
              </p>
            </div>

            <MarkdownEditor
              label="Post summary prompt"
              ariaLabel="Post summary prompt"
              value={form.analysis_summary_prompt}
              rows={8}
              helpText="Instructions for the summary_ru field. Leave blank to reset to the default."
              onChange={(value) => {
                setForm((current) => (current ? { ...current, analysis_summary_prompt: value } : current));
              }}
            />

            <MarkdownEditor
              label="Verdict reason prompt"
              ariaLabel="Verdict reason prompt"
              value={form.analysis_verdict_reason_prompt}
              rows={4}
              helpText="Instructions for the verdict_reason field. Leave blank to reset to the default."
              onChange={(value) => {
                setForm((current) =>
                  current ? { ...current, analysis_verdict_reason_prompt: value } : current
                );
              }}
            />
          </section>

          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <button
              disabled={saving || testingEmail}
              type="submit"
              style={{
                backgroundColor: theme.color.accent,
                border: "none",
                borderRadius: theme.radius.card,
                color: "#ffffff",
                cursor: "pointer",
                fontFamily: "inherit",
                padding: "10px 18px"
              }}
            >
              {saving ? "Saving settings..." : "Save settings"}
            </button>
            <button
              disabled={saving || testingEmail}
              onClick={() => {
                void handleTestEmail();
              }}
              type="button"
              style={{
                backgroundColor: theme.color.accent,
                border: "none",
                borderRadius: theme.radius.card,
                color: "#ffffff",
                cursor: "pointer",
                fontFamily: "inherit",
                padding: "10px 18px"
              }}
            >
              {testingEmail ? "Sending test email..." : "Send test email"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
