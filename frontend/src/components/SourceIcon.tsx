import { useState } from "react";

import { faviconUrl } from "../lib/favicon";
import { theme } from "../styles/theme";

type SourceIconProps = {
  /** A source or article URL; its hostname determines which favicon to show. */
  url: string | null | undefined;
  /** Rendered box size in px. */
  size?: number;
  /** Tooltip / accessible label (usually the source name). */
  title?: string;
};

/** A small site favicon with a neutral globe fallback when none can be loaded. */
export function SourceIcon({ url, size = 16, title }: SourceIconProps) {
  const [failed, setFailed] = useState(false);
  // Request a 2x icon so it stays crisp on hi-dpi displays.
  const src = faviconUrl(url, Math.max(32, size * 2));

  const box: React.CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
    flexShrink: 0,
    borderRadius: "3px",
    display: "block"
  };

  if (!src || failed) {
    return (
      <svg
        viewBox="0 0 16 16"
        fill="none"
        stroke={theme.color.muted}
        strokeWidth="1.4"
        style={box}
        aria-hidden="true"
      >
        <title>{title ?? "Source"}</title>
        <circle cx="8" cy="8" r="6.5" />
        <path d="M1.5 8h13M8 1.5c2 2 2 11 0 13M8 1.5c-2 2-2 11 0 13" />
      </svg>
    );
  }

  return (
    <img
      src={src}
      alt=""
      title={title}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{ ...box, objectFit: "contain" }}
    />
  );
}
