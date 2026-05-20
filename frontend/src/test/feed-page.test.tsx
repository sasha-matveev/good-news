import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

function createDeferredResponse(body: unknown, status = 200) {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((innerResolve) => {
    resolve = innerResolve;
  });

  return {
    promise,
    resolve: () => {
      resolve(new Response(JSON.stringify(body), { status }));
    }
  };
}

const BASE_POST = {
  id: 2,
  source_id: 2,
  source_name: "Beta",
  canonical_url: "https://beta.example/posts/newer",
  title: "Newer",
  published_at: "2026-04-20T09:00:00Z",
  raw_content: "Fresh enough for the default window.",
  feedback_state: null,
  read_later: false,
  summary_ru: "Разбор подходов для Beta.",
  verdict: "interesting",
  verdict_reason: "High practical backend value.",
  ranking_explanation: "feedback=none; topic_affinity=0.9"
};

const OLDER_POST = {
  id: 1,
  source_id: 1,
  source_name: "Alpha",
  canonical_url: "https://alpha.example/posts/older",
  title: "Older",
  published_at: "2026-03-01T08:00:00Z",
  raw_content: "Shown only in the all-posts window.",
  feedback_state: "interesting",
  read_later: false,
  summary_ru: "Русское summary for Alpha.",
  verdict: "interesting",
  verdict_reason: "High operator relevance.",
  ranking_explanation: "feedback=interesting; source_affinity=0.4"
};

function makeUrlMock(handlers: Record<string, unknown | (() => Promise<Response>)>) {
  return vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);
    for (const [pattern, value] of Object.entries(handlers)) {
      if (urlStr.includes(pattern)) {
        if (typeof value === "function") return (value as () => Promise<Response>)();
        return Promise.resolve(new Response(JSON.stringify(value), { status: 200 }));
      }
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });
}

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

test("feed page renders feed-only sort controls on the same toolbar row as filters", async () => {
  const fetchMock = makeUrlMock({
    "/api/posts": [BASE_POST]
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("Newer")).toBeInTheDocument();

  const toolbar = screen.getByTestId("feed-toolbar");
  const [filtersGroup, sortingGroup] = Array.from(toolbar.children) as HTMLElement[];

  expect(within(filtersGroup).getByRole("button", { name: "All" })).toBeInTheDocument();
  expect(within(filtersGroup).getByRole("button", { name: "Interesting" })).toBeInTheDocument();
  expect(within(filtersGroup).getByRole("button", { name: "Not interesting" })).toBeInTheDocument();
  expect(within(filtersGroup).getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  expect(within(sortingGroup).getByRole("button", { name: "By match" })).toBeInTheDocument();
  expect(within(sortingGroup).getByRole("button", { name: "By date" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Monitoring" }));

  expect(screen.queryByRole("button", { name: "By match" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "By date" })).not.toBeInTheDocument();
});

test("feed page loads default posts, shows the redesigned card content, and can request all collected posts", async () => {
  const fetchMock = makeUrlMock({
    "window=all": [OLDER_POST, BASE_POST],
    "/api/posts": [BASE_POST]
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  // Default window is "all" — both posts load immediately
  expect(await screen.findByText("Newer")).toBeInTheDocument();
  expect(await screen.findByText("Older")).toBeInTheDocument();
  expect(screen.getByText(/match 9\/10/i)).toBeInTheDocument();
  expect(screen.getByText("Разбор подходов для Beta.")).toBeInTheDocument();
  const readArticleLinks = screen.getAllByRole("link", { name: /read article/i });
  expect(readArticleLinks.some((l) => l.getAttribute("href") === "https://beta.example/posts/newer")).toBe(true);

  // Switch to Last month — only the recent post (BASE_POST) remains
  fireEvent.click(screen.getByRole("button", { name: "Last month" }));

  await waitFor(() => expect(screen.queryByText("Older")).not.toBeInTheDocument());
  expect(screen.getByText("Newer")).toBeInTheDocument();
  expect(screen.getByText("Разбор подходов для Beta.")).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=all&sort=date&limit=50", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=last_month&sort=date&limit=50", { method: "GET" });
  });
});

test("feed page lets the user save feedback on a post and shows the persisted state again after reload", async () => {
  const POST_NO_FEEDBACK = { ...BASE_POST, summary_ru: null, ranking_explanation: "feedback=none; topic_affinity=0.6" };
  const POST_WITH_FEEDBACK = { ...POST_NO_FEEDBACK, feedback_state: "interesting", ranking_explanation: "feedback=interesting; topic_affinity=0.6" };

  const fetchMock = vi
    .fn<typeof fetch>()
    .mockImplementation((url, init) => {
      const urlStr = typeof url === "string" ? url : String(url);
      if (urlStr.includes("/api/feedback/")) {
        return Promise.resolve(new Response(JSON.stringify({ post_id: 2, state: "interesting" }), { status: 200 }));
      }
      if (urlStr.includes("/api/posts")) {
        const alreadyLiked = (fetchMock.mock.calls.filter(([u]) => String(u).includes("/api/feedback")).length) > 0;
        return Promise.resolve(new Response(JSON.stringify([alreadyLiked ? POST_WITH_FEEDBACK : POST_NO_FEEDBACK]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });

  vi.stubGlobal("fetch", fetchMock);

  const firstRender = render(<AppShell />);

  expect(await screen.findByText("Newer")).toBeInTheDocument();

  // [1] skips the filter tab button; PostCard feedback button comes second in DOM order
  fireEvent.click(screen.getAllByRole("button", { name: "Interesting" })[1]);

  await waitFor(() => {
    expect(screen.getAllByRole("button", { name: "Interesting" })[1]).toHaveAttribute("aria-pressed", "true");
  });

  firstRender.unmount();
  render(<AppShell />);

  await waitFor(() => {
    expect(screen.getAllByRole("button", { name: "Interesting" })[1]).toHaveAttribute("aria-pressed", "true");
  });

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=all&sort=date&limit=50", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/feedback/2", {
      body: JSON.stringify({ state: "interesting" }),
      headers: { "Content-Type": "application/json" },
      method: "PUT"
    });
  });
});

test("feed page shows active loading feedback while refreshing results and saving a post action", async () => {
  const refreshResponse = createDeferredResponse([OLDER_POST]);
  const saveResponse = createDeferredResponse({ post_id: 1, state: "not_interesting" });

  const initialPost = { ...BASE_POST, summary_ru: null, ranking_explanation: "feedback=none; topic_affinity=0.6" };

  const fetchMock = vi
    .fn<typeof fetch>()
    .mockImplementation((url, init) => {
      const urlStr = typeof url === "string" ? url : String(url);
      if (urlStr.includes("/api/monitoring/summary")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (urlStr.includes("/api/feedback/")) {
        return saveResponse.promise;
      }
      // Feed default load (window=all&sort=date) — immediate response
      if (urlStr.includes("window=all")) {
        return Promise.resolve(new Response(JSON.stringify([initialPost]), { status: 200 }));
      }
      // Last month filter (no window param) — deferred response
      return refreshResponse.promise;
    });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("Newer")).toBeInTheDocument();

  // Switch from All time (default) to Last month — triggers deferred fetch
  fireEvent.click(screen.getByRole("button", { name: "Last month" }));

  expect(screen.getByRole("status")).toHaveTextContent("Refreshing posts...");
  expect(screen.getByRole("button", { name: "Loading last month posts..." })).toBeDisabled();
  expect(screen.getByText("Newer")).toBeInTheDocument();

  refreshResponse.resolve();

  expect(await screen.findByText("Older")).toBeInTheDocument();

  // [1] skips the filter tab button; PostCard feedback button comes second in DOM order
  fireEvent.click(screen.getAllByRole("button", { name: "Not interesting" })[1]);

  expect(screen.getAllByRole("button", { name: "Not interesting" })[1]).toBeDisabled();

  saveResponse.resolve();

  await waitFor(() => {
    expect(screen.getAllByRole("button", { name: "Not interesting" })[1]).toHaveAttribute("aria-pressed", "true");
  });
});
