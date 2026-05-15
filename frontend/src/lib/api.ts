export type SourceRecord = {
  id: number;
  display_name: string | null;
  original_url: string;
  feed_url: string | null;
  strategy_kind: string | null;
  active: boolean;
  status: string;
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
  raw_content: string;
  feedback_state: string | null;
  read_later: boolean;
  summary_ru: string | null;
  verdict: string | null;
  verdict_reason: string | null;
  ranking_explanation: string | null;
};

export type FeedbackState = "interesting" | "not_interesting" | "want_to_read" | "norm";
export type PostSortMode = "match" | "date";

export type WantToReadUpdate = {
  post_id: number;
  saved: boolean;
  feedback_state: FeedbackState | null;
};

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

const API_ROOT = "/api";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listSources(): Promise<SourceRecord[]> {
  const response = await fetch(`${API_ROOT}/sources`, { method: "GET" });
  return readJson<SourceRecord[]>(response);
}

export async function createSource(url: string): Promise<SourceRecord> {
  const response = await fetch(`${API_ROOT}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  return readJson<SourceRecord>(response);
}

export async function updateSourceActive(
  sourceId: number,
  active: boolean
): Promise<SourceRecord> {
  const response = await fetch(`${API_ROOT}/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active })
  });
  return readJson<SourceRecord>(response);
}

export async function runSourceSyncOnce(): Promise<SourceSyncRecord> {
  const response = await fetch(`${API_ROOT}/sources/sync`, {
    method: "POST"
  });
  return readJson<SourceSyncRecord>(response);
}

export async function listPosts(params?: {
  sourceId?: number;
  feedbackState?: string;
  window?: "last_month" | "all";
  sort?: PostSortMode;
}): Promise<PostRecord[]> {
  const search = new URLSearchParams();
  if (params?.sourceId !== undefined) {
    search.set("source_id", String(params.sourceId));
  }
  if (params?.feedbackState) {
    search.set("feedback_state", params.feedbackState);
  }
  if (params?.window === "all") {
    search.set("window", "all");
  }
  if (params?.sort) {
    search.set("sort", params.sort);
  }

  const suffix = search.toString() ? `?${search.toString()}` : "";
  const response = await fetch(`${API_ROOT}/posts${suffix}`, { method: "GET" });
  return readJson<PostRecord[]>(response);
}

export async function updateFeedback(
  postId: number,
  state: FeedbackState
): Promise<{ post_id: number; state: FeedbackState }> {
  const response = await fetch(`${API_ROOT}/feedback/${postId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state })
  });
  return readJson<{ post_id: number; state: FeedbackState }>(response);
}

export async function updateWantToRead(
  postId: number,
  saved: boolean
): Promise<WantToReadUpdate> {
  const response = await fetch(`${API_ROOT}/want-to-read/${postId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ saved })
  });
  return readJson<WantToReadUpdate>(response);
}

export async function getPreferenceProfile(): Promise<PreferenceProfileRecord> {
  const response = await fetch(`${API_ROOT}/preferences`, { method: "GET" });
  return readJson<PreferenceProfileRecord>(response);
}

export async function getSettings(): Promise<SettingsRecord> {
  const response = await fetch(`${API_ROOT}/settings`, { method: "GET" });
  return readJson<SettingsRecord>(response);
}

export async function listDigests(): Promise<DigestListItemRecord[]> {
  const response = await fetch(`${API_ROOT}/digests`, { method: "GET" });
  return readJson<DigestListItemRecord[]>(response);
}

export async function getDigest(digestId: number): Promise<DigestDetailRecord> {
  const response = await fetch(`${API_ROOT}/digests/${digestId}`, { method: "GET" });
  return readJson<DigestDetailRecord>(response);
}

export async function updateSettings(payload: SettingsUpdate): Promise<SettingsRecord> {
  const response = await fetch(`${API_ROOT}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readJson<SettingsRecord>(response);
}

export async function sendTestEmail(): Promise<{ status: string }> {
  const response = await fetch(`${API_ROOT}/settings/test-email`, { method: "POST" });
  return readJson<{ status: string }>(response);
}

export async function setReadLater(
  postId: number,
  saved: boolean
): Promise<{ post_id: number; read_later: boolean }> {
  const response = await fetch(`${API_ROOT}/posts/${postId}/read-later`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ saved })
  });
  return readJson<{ post_id: number; read_later: boolean }>(response);
}

export async function recordArticleOpen(
  postId: number
): Promise<{ opened: boolean }> {
  const response = await fetch(`${API_ROOT}/posts/${postId}/open`, {
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
    const response = await fetch("/api/monitoring/summary", { method: "GET" });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    return data as MonitoringSummary;
  } catch {
    return null;
  }
}
