import { describe, expect, it } from "vitest";

import { buildMatchScore } from "../components/PostCard";
import type { PostRecord } from "../lib/api";

function makePost(overrides: Partial<PostRecord>): PostRecord {
  return {
    id: 1,
    source_id: 1,
    source_name: "Test",
    canonical_url: "https://example.com",
    title: "Test Post",
    published_at: "2026-05-15T10:00:00Z",
    raw_content: "content",
    feedback_state: null,
    read_later: false,
    summary_ru: null,
    verdict: null,
    verdict_reason: null,
    ranking_explanation: null,
    ...overrides,
  };
}

describe("buildMatchScore", () => {
  // interesting/want_to_read feedbackScore (4.0/5.0) * 10 always exceeds the 10/10 cap,
  // so liked posts are always 10/10 regardless of content scores.
  it("liked posts always show 10/10 regardless of content signals", () => {
    const noContentScore = buildMatchScore(makePost({
      feedback_state: "interesting",
      ranking_explanation: "feedback=interesting; source_affinity=0.0; topic_affinity=0.0",
    }));
    expect(noContentScore).toBe(10);
  });

  it("posts with no feedback are scored by content signals only", () => {
    const lowContent = buildMatchScore(makePost({
      ranking_explanation: "feedback=none; source_affinity=0.0; topic_affinity=0.0; recency=0.1",
    }));
    const highContent = buildMatchScore(makePost({
      ranking_explanation: "feedback=none; source_affinity=0.4; topic_affinity=0.9; recency=0.3",
    }));
    expect(highContent).toBeGreaterThan(lowContent);
  });

  it("not_interesting posts score lower than posts with no feedback for the same content signals", () => {
    const base = "source_affinity=0.3; topic_affinity=0.2; format_affinity=0.1; practical=0.1; depth=0.1; recency=0.1";
    const noFeedbackScore = buildMatchScore(makePost({
      ranking_explanation: `feedback=none; ${base}`,
    }));
    const dislikedScore = buildMatchScore(makePost({
      feedback_state: "not_interesting",
      ranking_explanation: `feedback=not_interesting; ${base}`,
    }));
    expect(dislikedScore).toBeLessThan(noFeedbackScore);
  });

  it("not_interesting with small content signals clamps to 0", () => {
    const score = buildMatchScore(makePost({
      feedback_state: "not_interesting",
      ranking_explanation: "feedback=not_interesting; source_affinity=0.1; topic_affinity=0.1",
    }));
    expect(score).toBe(0);
  });

  it("score is clamped to 10 at the top", () => {
    const score = buildMatchScore(makePost({
      feedback_state: "interesting",
      ranking_explanation: "feedback=interesting; source_affinity=9.9; topic_affinity=9.9",
    }));
    expect(score).toBe(10);
  });

  it("null explanation yields 0", () => {
    expect(buildMatchScore(makePost({ ranking_explanation: null }))).toBe(0);
  });
});
