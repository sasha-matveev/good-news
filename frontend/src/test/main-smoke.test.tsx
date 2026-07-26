import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

const smoke = vi.hoisted(() => {
  const authListener = {
    current: undefined as ((user: unknown) => void) | undefined
  };
  const rootRender = vi.fn();

  return {
    authListener,
    createRoot: vi.fn(() => ({ render: rootRender })),
    rootRender,
    signInWithGoogle: vi.fn(() => Promise.resolve()),
    watchUser: vi.fn((listener: (user: unknown) => void) => {
      authListener.current = listener;
      return vi.fn();
    })
  };
});

vi.mock("react-dom/client", () => ({
  default: { createRoot: smoke.createRoot }
}));

vi.mock("../lib/firebase", () => ({
  currentIdToken: vi.fn(() => Promise.resolve(null)),
  signInWithGoogle: smoke.signInWithGoogle,
  watchUser: smoke.watchUser
}));

const SMOKE_POST = {
  id: 79,
  source_id: 1,
  source_name: "React",
  canonical_url: "https://react.dev/blog/2024/12/05/react-19",
  title: "React 19 migration smoke post",
  published_at: "2026-07-26T09:00:00Z",
  published_at_source: "feed",
  raw_content: "Verifies the production application path.",
  feedback_state: null,
  read_later: false,
  summary_ru: null,
  verdict: null,
  verdict_reason: null,
  relevance_score: 10,
  ranking_explanation: null
};

test("production bootstrap supports authentication, feed rendering, and a primary interaction", async () => {
  document.body.innerHTML = '<div id="root"></div>';
  window.history.replaceState({}, "", "/feed");

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const path = String(url);
    if (path.includes("/api/monitoring/summary")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            sources_active: 1,
            sources_total: 1,
            last_sync_at: "2026-07-26T09:00:00Z"
          }),
          { status: 200 }
        )
      );
    }
    if (path.includes("/api/feedback/79")) {
      return Promise.resolve(
        new Response(JSON.stringify({ post_id: 79, state: "interesting" }), { status: 200 })
      );
    }
    if (path.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([SMOKE_POST]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);

  await import("../main");

  const rootElement = document.getElementById("root");
  expect(smoke.createRoot).toHaveBeenCalledWith(rootElement);
  expect(smoke.rootRender).toHaveBeenCalledOnce();

  render(smoke.rootRender.mock.calls[0][0] as ReactNode);
  expect(screen.getByText("Loading…")).toBeInTheDocument();

  act(() => {
    smoke.authListener.current?.(null);
  });

  fireEvent.click(screen.getByRole("button", { name: "Sign in with Google" }));
  expect(smoke.signInWithGoogle).toHaveBeenCalledOnce();

  act(() => {
    smoke.authListener.current?.({ uid: "smoke-user" });
  });

  const title = await screen.findByText("React 19 migration smoke post");
  const post = title.closest("article");
  expect(post).not.toBeNull();

  fireEvent.click(within(post as HTMLElement).getByRole("button", { name: "Interesting" }));

  await waitFor(() => {
    expect(within(post as HTMLElement).getByRole("button", { name: "Interesting" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
  expect(fetchMock).toHaveBeenCalledWith("/api/feedback/79", {
    body: JSON.stringify({ state: "interesting" }),
    headers: { "Content-Type": "application/json" },
    method: "PUT"
  });
});
