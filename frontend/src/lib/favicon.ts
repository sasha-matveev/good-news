/**
 * Build a favicon URL for the site that owns `pageUrl`, via Google's public
 * favicon service. Sources rarely expose a logo through the feed, but every
 * site has a favicon, so we derive the icon from the page/source hostname.
 *
 * Returns "" when no usable hostname can be derived (caller should fall back
 * to a placeholder).
 */
export function faviconUrl(pageUrl: string | null | undefined, size = 32): string {
  if (!pageUrl) return "";
  try {
    const withScheme = pageUrl.includes("://") ? pageUrl : `https://${pageUrl}`;
    const { hostname } = new URL(withScheme);
    if (!hostname) return "";
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=${size}`;
  } catch {
    return "";
  }
}
