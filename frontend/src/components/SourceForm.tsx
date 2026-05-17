import { FormEvent, useState } from "react";
import { theme } from "../styles/theme";

type SourceFormProps = {
  disabled?: boolean;
  submitLabel?: string;
  onSubmit: (url: string) => Promise<void>;
};

export function SourceForm({
  disabled = false,
  submitLabel = "Add source",
  onSubmit
}: SourceFormProps) {
  const [url, setUrl] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      return;
    }
    await onSubmit(trimmed);
    setUrl("");
  }

  return (
    <form
      onSubmit={(event) => {
        void handleSubmit(event);
      }}
      style={{
        display: "grid",
        gap: "12px",
        marginBottom: "24px"
      }}
    >
      <label
        htmlFor="source-url"
        style={{ fontSize: "15px", fontWeight: 600 }}
      >
        Source URL
      </label>
      <div
        style={{
          display: "grid",
          gap: "12px",
          gridTemplateColumns: "minmax(0, 1fr) auto"
        }}
      >
        <input
          id="source-url"
          type="text"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
          }}
          placeholder="https://example.com/blog"
          disabled={disabled}
          style={{
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            fontFamily: "inherit",
            fontSize: "15px",
            padding: "12px 14px"
          }}
        />
        <button
          type="submit"
          disabled={disabled}
          style={{
            backgroundColor: theme.color.accent,
            border: `1px solid ${theme.color.accent}`,
            borderRadius: theme.radius.card,
            color: theme.color.card,
            cursor: disabled ? "wait" : "pointer",
            fontFamily: "inherit",
            fontSize: "15px",
            padding: "12px 18px"
          }}
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
