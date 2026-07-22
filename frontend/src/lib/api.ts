export type SourceRecord = {
  id: number;
  display_name: string | null;
  original_url: string;
  feed_url: string | null;
  strategy_kind: string | null;
  active: boolean;
  status: string;
  post_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  needs_readaptation: boolean;
  readaptation_reason: string | null;
};

export type SourceSyncRecord = {
  processed_source_ids: number[];
};

export type PostRecord = {
  id: number;
  source_id: number;
  source_name: string | null;
  canonical_url: string;
  title: string;
  published_at: string | null;
  /** How the date was obtained: "feed" | "json_ld" | "meta_og" | "meta_date" | "time_element" | "none" | null (old posts without this metadata) */
  published_at_source: string | null;
  raw_content: string;
  feedback_state: string | null;
  read_later: boolean;
  summary_ru: string | null;
  verdict: string | null;
  verdict_reason: string | null;
  /** AI profile-aware match score 0–10; null when the post has not been analyzed yet. */
  relevance_score: number | null;
  ranking_explanation: string | null;
};

export type FeedbackState = "interesting" | "not_interesting" | "want_to_read" | "norm";
export type PostSortMode = "match" | "date";

export type PreferenceProfileRecord = {
  summary: string;
  positive_signals: string[];
  negative_signals: string[];
  learning_proof: string[];
  feedback_totals: {
    total: number;
    interesting: number;
    want_to_read: number;
    not_interesting: number;
  };
};

export type SettingsRecord = {
  daily_digest_time: string;
  weekly_digest_day_of_week: WeeklyDigestDayOfWeek;
  weekly_digest_time: string;
  observability_dashboard_url?: string | null;
  recipient_email: string | null;
  sender_identity: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_security_mode: "none" | "starttls" | "ssl";
  daily_digest_enabled: boolean;
  daily_digest_catch_up_enabled: boolean;
  weekly_digest_enabled: boolean;
  weekly_digest_catch_up_enabled: boolean;
  smtp_password_configured: boolean;
  analysis_summary_prompt: string;
  analysis_verdict_reason_prompt: string;
};

export type WeeklyDigestDayOfWeek =
  | "mon"
  | "tue"
  | "wed"
  | "thu"
  | "fri"
  | "sat"
  | "sun";

export type SettingsUpdate = {
  daily_digest_time: string;
  weekly_digest_day_of_week: WeeklyDigestDayOfWeek;
  weekly_digest_time: string;
  recipient_email: string | null;
  sender_identity: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_security_mode: "none" | "starttls" | "ssl";
  daily_digest_enabled: boolean;
  daily_digest_catch_up_enabled: boolean;
  weekly_digest_enabled: boolean;
  weekly_digest_catch_up_enabled: boolean;
  smtp_password?: string;
  analysis_summary_prompt: string;
  analysis_verdict_reason_prompt: string;
};

export type DigestListItemRecord = {
  id: number;
  digest_type: string;
  status: string;
  sent_at: string | null;
  included_post_count: number;
};

export type DigestIncludedPostRecord = {
  post_id: number;
  title: string;
  feedback_state?: FeedbackState | null;
};

export type DigestDetailRecord = {
  id: number;
  digest_type: string;
  status: string;
  sent_at: string | null;
  title: string;
  included_posts: DigestIncludedPostRecord[];
  rendered_html: string;
};

export type BackendOwner = "python" | "java";

/**
 * Versioned production control plane for browser API ownership.
 *
 * PR-19 intentionally keeps every operation on Python. Later strangler phases
 * change individual values in this map only after the matching Java operation
 * has passed parity and production-readiness checks.
 */
export const API_OPERATION_OWNERS = {
  listSources: "python",
  createSource: "python",
  deleteSource: "python",
  updateSourceActive: "python",
  runSourceSyncOnce: "python",
  syncSource: "python",
  reloadPosts: "python",
  listPosts: "python",
  updateFeedback: "python",
  getPreferenceProfile: "python",
  recomputePreferenceProfile: "python",
  getSettings: "python",
  listDigests: "python",
  getDigest: "python",
  updateSettings: "python",
  sendTestEmail: "python",
  setReadLater: "python",
  recordArticleOpen: "python",
  fetchMonitoringSummary: "python",
  getSourceLog: "python",
  getAnalysisQueue: "python",
  analyzePendingNow: "python"
} as const satisfies Record<string, BackendOwner>;

export type ApiOperation = keyof typeof API_OPERATION_OWNERS;

const API_ORIGINS: Record<BackendOwner, string> = {
  python: normalizeOrigin(import.meta.env.VITE_CONTENT_API_ORIGIN as string | undefined),
  java: normalizeOrigin(import.meta.env.VITE_JAVA_API_ORIGIN as string | undefined)
};

function normalizeOrigin(origin: string | undefined): string {
  return (origin ?? "").trim().replace(/\/+$/, "");
}

function diagnosticOverride(): BackendOwner | null {
  const override = (import.meta.env.VITE_API_BACKEND_OVERRIDE as string | undefined)?.trim();
  if (override !== "python" && override !== "java") return null;

  const deployEnvironment = (
    (import.meta.env.VITE_DEPLOY_ENV as string | undefined) ?? import.meta.env.MODE
  ).toLowerCase();
  const overrideAllowed = ["development", "test", "local", "preview", "staging"].includes(
    deployEnvironment
  );
  return overrideAllowed ? override : null;
}

function apiUrl(operation: ApiOperation, path: string): string {
  const owner = diagnosticOverride() ?? API_OPERATION_OWNERS[operation];
  return `${API_ORIGINS[owner]}/api${path}`;
}

async function apiFetch(
  operation: ApiOperation,
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  let token: string | null = null;
  try {
    const { currentIdToken } = await import("./firebase");
    token = await currentIdToken();
  } catch {
    // Firebase unavailable (tests, local dev without auth) — send the request as-is.
  }
  if (!token) {
    return fetch(apiUrl(operation, path), init);
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(apiUrl(operation, path), { ...init, headers });
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listSources(): Promise<SourceRecord[]> {
  const response = await apiFetch("listSources", "/sources", { method: "GET" });
  return readJson<SourceRecord[]>(response);
}

export async function createSource(url: string): Promise<SourceRecord> {
  const response = await apiFetch("createSource", "/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  return readJson<SourceRecord>(response);
}

export async function deleteSource(sourceId: number): Promise<void> {
  const response = await apiFetch("deleteSource", `/sources/${sourceId}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
}

export async function updateSourceActive(
  sourceId: number,
  active: boolean
): Promise<SourceRecord> {
  const response = await apiFetch("updateSourceActive", `/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active })
  });
  return readJson<SourceRecord>(response);
}

export async function runSourceSyncOnce(): Promise<SourceSyncRecord> {
  const response = await apiFetch("runSourceSyncOnce", "/sources/sync", {
    method: "POST"
  });
  return readJson<SourceSyncRecord>(response);
}

export async function syncSource(sourceId: number): Promise<SourceSyncRecord> {
  const response = await apiFetch("syncSource", `/sources/${sourceId}/sync`, {
    method: "POST"
  });
  return readJson<SourceSyncRecord>(response);
}

export type ReloadPostsResult = { deleted: number; reloaded: number };

export async function reloadPosts(sourceId: number): Promise<ReloadPostsResult> {
  const response = await apiFetch("reloadPosts", `/sources/${sourceId}/reload-posts`, {
    method: "POST"
  });
  return readJson<ReloadPostsResult>(response);
}

export async function listPosts(params?: {
  sourceId?: number;
  feedbackState?: string;
  window?: "last_month" | "all";
  sort?: PostSortMode;
  limit?: number;
  offset?: number;
  readLater?: boolean;
}): Promise<PostRecord[]> {
  const search = new URLSearchParams();
  if (params?.sourceId !== undefined) {
    search.set("source_id", String(params.sourceId));
  }
  if (params?.feedbackState) {
    search.set("feedback_state", params.feedbackState);
  }
  if (params?.window) {
    search.set("window", params.window);
  }
  if (params?.sort) {
    search.set("sort", params.sort);
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params?.offset !== undefined && params.offset > 0) {
    search.set("offset", String(params.offset));
  }
  if (params?.readLater !== undefined) {
    search.set("read_later", String(params.readLater));
  }

  const suffix = search.toString() ? `?${search.toString()}` : "";
  const response = await apiFetch("listPosts", `/posts${suffix}`, { method: "GET" });
  return readJson<PostRecord[]>(response);
}

export async function updateFeedback(
  postId: number,
  state: FeedbackState
): Promise<{ post_id: number; state: FeedbackState }> {
  const response = await apiFetch("updateFeedback", `/feedback/${postId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state })
  });
  return readJson<{ post_id: number; state: FeedbackState }>(response);
}

export async function getPreferenceProfile(): Promise<PreferenceProfileRecord> {
  const response = await apiFetch("getPreferenceProfile", "/preferences", { method: "GET" });
  return readJson<PreferenceProfileRecord>(response);
}

export async function recomputePreferenceProfile(): Promise<PreferenceProfileRecord> {
  const response = await apiFetch("recomputePreferenceProfile", "/preferences/recompute", {
    method: "POST"
  });
  return readJson<PreferenceProfileRecord>(response);
}

export async function getSettings(): Promise<SettingsRecord> {
  const response = await apiFetch("getSettings", "/settings", { method: "GET" });
  return readJson<SettingsRecord>(response);
}

export async function listDigests(): Promise<DigestListItemRecord[]> {
  const response = await apiFetch("listDigests", "/digests", { method: "GET" });
  return readJson<DigestListItemRecord[]>(response);
}

export async function getDigest(digestId: number): Promise<DigestDetailRecord> {
  const response = await apiFetch("getDigest", `/digests/${digestId}`, { method: "GET" });
  return readJson<DigestDetailRecord>(response);
}

export async function updateSettings(payload: SettingsUpdate): Promise<SettingsRecord> {
  const response = await apiFetch("updateSettings", "/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readJson<SettingsRecord>(response);
}

export async function sendTestEmail(): Promise<{ status: string }> {
  const response = await apiFetch("sendTestEmail", "/settings/test-email", { method: "POST" });
  return readJson<{ status: string }>(response);
}

export async function setReadLater(
  postId: number,
  saved: boolean
): Promise<{ post_id: number; read_later: boolean }> {
  const response = await apiFetch("setReadLater", `/posts/${postId}/read-later`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ saved })
  });
  return readJson<{ post_id: number; read_later: boolean }>(response);
}

export async function recordArticleOpen(
  postId: number
): Promise<{ opened: boolean }> {
  const response = await apiFetch("recordArticleOpen", `/posts/${postId}/open`, {
    method: "POST"
  });
  return readJson<{ opened: boolean }>(response);
}

export type ServiceHealth = "ok" | "error";

export type MonitoringSummary = {
  sources_active: number;
  sources_total: number;
  posts_total: number;
  posts_unranked: number;
  last_sync_at: string | null;
  services: {
    content_api: ServiceHealth;
    analysis_llm: ServiceHealth;
    source_ingestion: ServiceHealth;
    delivery: ServiceHealth;
  };
};

export async function fetchMonitoringSummary(): Promise<MonitoringSummary | null> {
  try {
    const response = await apiFetch("fetchMonitoringSummary", "/monitoring/summary", {
      method: "GET"
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    return data as MonitoringSummary;
  } catch {
    return null;
  }
}

export type SourceLogLine = { ts: number; msg: string };
export type SourceLogRecord = { log: SourceLogLine[]; done: boolean; status: string | null };

export async function getSourceLog(sourceId: number): Promise<SourceLogRecord> {
  const response = await apiFetch("getSourceLog", `/sources/${sourceId}/log`, { method: "GET" });
  return readJson<SourceLogRecord>(response);
}

export type QueueItem = { post_id: number; title: string; source_name: string | null; created_at: string | null };

export async function getAnalysisQueue(): Promise<QueueItem[]> {
  const response = await apiFetch("getAnalysisQueue", "/monitoring/queue", { method: "GET" });
  return readJson<QueueItem[]>(response);
}

export type AnalyzeNowResult = { analyzed: number; remaining: number };

export async function analyzePendingNow(): Promise<AnalyzeNowResult> {
  const response = await apiFetch("analyzePendingNow", "/monitoring/analyze-now", {
    method: "POST"
  });
  return readJson<AnalyzeNowResult>(response);
}
