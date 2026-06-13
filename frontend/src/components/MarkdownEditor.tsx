import { useState } from "react";
import { marked } from "marked";

import { theme } from "../styles/theme";

type MarkdownEditorProps = {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  helpText?: string;
  ariaLabel?: string;
};

const MONO_FONT = "'Consolas', 'Menlo', 'Monaco', monospace";

type EditorMode = "edit" | "preview";

function pillStyle(active: boolean) {
  return {
    backgroundColor: active ? theme.color.accent : theme.color.card,
    border: `1px solid ${active ? theme.color.accent : theme.color.border}`,
    borderRadius: theme.radius.card,
    color: active ? "#ffffff" : theme.color.text,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: "12px",
    padding: "4px 12px"
  } as const;
}

export function MarkdownEditor({
  label,
  value,
  onChange,
  rows = 8,
  helpText,
  ariaLabel
}: MarkdownEditorProps) {
  const [mode, setMode] = useState<EditorMode>("edit");

  // The content is admin-authored prompt text in a single-user app, so the
  // rendered Markdown is not sanitized. If this editor is ever exposed to
  // untrusted authors, pipe the output through a sanitizer (e.g. DOMPurify).
  const renderedHtml = marked.parse(value || "_Nothing to preview yet._", { async: false }) as string;

  return (
    <div style={{ display: "grid", gap: "8px" }}>
      <div style={{ alignItems: "center", display: "flex", gap: "10px", justifyContent: "space-between" }}>
        {label ? <span style={{ fontWeight: 600 }}>{label}</span> : <span />}
        <div role="tablist" aria-label="Editor mode" style={{ display: "flex", gap: "6px" }}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "edit"}
            onClick={() => setMode("edit")}
            style={pillStyle(mode === "edit")}
          >
            Edit
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "preview"}
            onClick={() => setMode("preview")}
            style={pillStyle(mode === "preview")}
          >
            Preview
          </button>
        </div>
      </div>

      {mode === "edit" ? (
        <textarea
          aria-label={ariaLabel ?? label}
          value={value}
          rows={rows}
          onChange={(event) => onChange(event.target.value)}
          style={{
            backgroundColor: theme.color.card,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            color: theme.color.text,
            fontFamily: MONO_FONT,
            fontSize: "13px",
            lineHeight: 1.5,
            padding: "10px",
            resize: "vertical",
            width: "100%"
          }}
        />
      ) : (
        <div
          // eslint-disable-next-line react/no-danger -- admin-authored prompt text, single-user app
          dangerouslySetInnerHTML={{ __html: renderedHtml }}
          style={{
            backgroundColor: theme.color.shell,
            border: `1px solid ${theme.color.border}`,
            borderRadius: theme.radius.card,
            color: theme.color.text,
            minHeight: `${rows * 1.5}em`,
            padding: "10px"
          }}
        />
      )}

      {helpText ? (
        <span style={{ color: theme.color.muted, fontSize: "12px" }}>{helpText}</span>
      ) : null}
    </div>
  );
}
