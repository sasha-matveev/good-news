import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PostCard } from "../components/PostCard";
import type { PostRecord } from "../lib/api";

function makePost(overrides: Partial<PostRecord> = {}): PostRecord {
  return {
    id: 1,
    source_id: 1,
    source_name: "Test",
    canonical_url: "https://example.com",
    title: "Test Post",
    published_at: "2026-05-15T10:00:00Z",
    published_at_source: null,
    raw_content: "content",
    feedback_state: null,
    read_later: false,
    summary_ru: null,
    verdict: null,
    verdict_reason: null,
    relevance_score: null,
    ranking_explanation: null,
    ...overrides,
  };
}

describe("PostCard match score", () => {
  it("shows the AI relevance score as the match badge", () => {
    render(<PostCard post={makePost({ relevance_score: 7 })} />);
    expect(screen.getByText("match 7/10")).toBeInTheDocument();
  });

  it("renders a real zero score rather than hiding it", () => {
    render(<PostCard post={makePost({ relevance_score: 0 })} />);
    expect(screen.getByText("match 0/10")).toBeInTheDocument();
  });

  it("hides the match badge until the post has been analyzed", () => {
    render(<PostCard post={makePost({ relevance_score: null })} />);
    expect(screen.queryByText(/\/10/)).not.toBeInTheDocument();
  });
});
