import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

const initialSources = [
  {
    id: 1,
    display_name: "Alpha",
    original_url: "https://alpha.example",
    feed_url: "https://alpha.example/feed.xml",
    strategy_kind: "feed",
    active: true,
    status: "ready",
    post_count: 0,
    last_success_at: "2026-04-26T08:30:00Z",
    last_failure_at: null,
    needs_readaptation: false,
    readaptation_reason: null
  },
  {
    id: 2,
    display_name: "Journal",
    original_url: "https://journal.example",
    feed_url: null,
    strategy_kind: "html",
    active: false,
    status: "needs_readaptation",
    post_count: 0,
    last_success_at: null,
    last_failure_at: "2026-04-26T09:45:00Z",
    needs_readaptation: true,
    readaptation_reason: "No usable feed discovered; HTML fallback requires monitoring."
  }
];

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

test("sources page loads source state, shows readaptation warnings, adds a source, and toggles active state", async () => {
  const newSource = {
    id: 3,
    display_name: "Example",
    original_url: "https://example.com",
    feed_url: "https://example.com/feed.xml",
    strategy_kind: "feed",
    active: true,
    status: "ready",
    post_count: 0,
    last_success_at: null,
    last_failure_at: null,
    needs_readaptation: false,
    readaptation_reason: null
  };

  const addedSourcesState = [...initialSources, newSource];

  let sourcesPostCount = 0;
  let sourcesPatchCount = 0;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.match(/\/api\/sources\/\d+/) && method === "PATCH") {
      sourcesPatchCount++;
      return Promise.resolve(
        new Response(JSON.stringify({ ...initialSources[0], active: false }), { status: 200 })
      );
    }
    if (urlStr === "/api/sources" && method === "POST") {
      sourcesPostCount++;
      return Promise.resolve(new Response(JSON.stringify(newSource), { status: 201 }));
    }
    if (urlStr === "/api/sources" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(initialSources), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(screen.getByText("Needs readaptation")).toBeInTheDocument();
  expect(
    screen.getByText("No usable feed discovered; HTML fallback requires monitoring.")
  ).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Source URL"), {
    target: { value: "example.com" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Add source" }));

  expect(await screen.findByText("Example")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Disable Alpha" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Enable Alpha" })).toBeInTheDocument();
  });

  expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=last_month&sort=date&limit=50", { method: "GET" });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources", { method: "GET" });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: "example.com" })
  });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources/1", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active: false })
  });
});

test("long source identity is constrained so actions remain visible", async () => {
  const longSource = {
    ...initialSources[0],
    display_name: "An exceptionally long source display name that must not push action buttons outside the card",
    original_url: "https://example.com/an/exceptionally/long/source/url/that/must/not/create/horizontal/scrolling"
  };

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);
    if (urlStr.includes("/api/monitoring/summary") || urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/sources") {
      return Promise.resolve(new Response(JSON.stringify([longSource]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);
  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  const title = await screen.findByText(longSource.display_name);
  const listGrid = title.closest("article")?.parentElement;
  const textContainer = title.parentElement;
  const identityGroup = textContainer?.parentElement;
  const sourceUrl = screen.getByRole("link", { name: longSource.original_url });
  const actionGroup = screen.getByRole("button", { name: `Sync ${longSource.display_name}` }).parentElement;

  expect(listGrid).toHaveStyle({ gridTemplateColumns: "minmax(0, 1fr)" });
  expect(identityGroup).toHaveStyle({ flex: "1 1 0", minWidth: "0", overflow: "hidden" });
  expect(textContainer).toHaveStyle({ flex: "1 1 0", minWidth: "0", overflow: "hidden" });
  expect(sourceUrl).toHaveStyle({
    display: "block",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap"
  });
  expect(actionGroup).toHaveStyle({ flexShrink: "0" });
});

test("sources page supports explicit sync so the first post becomes visible in Feed", async () => {
  const addedSource = {
    id: 1,
    display_name: "Example",
    original_url: "https://example.com",
    feed_url: "https://example.com/feed.xml",
    strategy_kind: "feed",
    active: true,
    status: "ready",
    post_count: 0,
    last_success_at: null,
    last_failure_at: null,
    needs_readaptation: false,
    readaptation_reason: null
  };

  const syncedSource = { ...addedSource, last_success_at: "2026-04-26T10:00:00Z" };

  const feedPost = {
    id: 1,
    source_id: 1,
    source_name: "Example",
    canonical_url: "https://example.com/posts/1",
    title: "First post",
    published_at: "2026-04-26T10:00:00Z",
    raw_content: "First useful excerpt.",
    feedback_state: null,
    summary_ru: null,
    verdict: null,
    verdict_reason: null,
    relevance_score: null,
    ranking_explanation: "feedback=none"
  };

  let sourcesGetCount = 0;
  let postsGetCount = 0;
  let sourcesPostDone = false;
  let syncDone = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts") && method === "GET") {
      postsGetCount++;
      const posts = syncDone ? [feedPost] : [];
      return Promise.resolve(new Response(JSON.stringify(posts), { status: 200 }));
    }
    if (urlStr === "/api/sources/sync" && method === "POST") {
      syncDone = true;
      return Promise.resolve(
        new Response(JSON.stringify({ processed_source_ids: [1] }), { status: 200 })
      );
    }
    if (urlStr === "/api/sources" && method === "POST") {
      sourcesPostDone = true;
      return Promise.resolve(new Response(JSON.stringify(addedSource), { status: 201 }));
    }
    if (urlStr === "/api/sources" && method === "GET") {
      sourcesGetCount++;
      const sources = sourcesPostDone ? (syncDone ? [syncedSource] : [addedSource]) : [];
      return Promise.resolve(new Response(JSON.stringify(sources), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("No collected posts in the last month.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  expect(await screen.findByText("No sources yet.")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Source URL"), {
    target: { value: "example.com" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Add source" }));

  expect(await screen.findByText("Example")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Sync sources now" }));

  expect(await screen.findByText("Sync complete for 1 source.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Feed" }));

  expect(await screen.findByText("First post")).toBeInTheDocument();

  expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=last_month&sort=date&limit=50", { method: "GET" });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources", { method: "GET" });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: "example.com" })
  });
  expect(fetchMock).toHaveBeenCalledWith("/api/sources/sync", { method: "POST" });
});

test("sources page shows in-flight labels for add, toggle, and sync operations", async () => {
  const addSourceResponse = createDeferredResponse({
    id: 3,
    display_name: "Example",
    original_url: "https://example.com",
    feed_url: "https://example.com/feed.xml",
    strategy_kind: "feed",
    active: true,
    status: "ready",
    post_count: 0,
    last_success_at: null,
    last_failure_at: null,
    needs_readaptation: false,
    readaptation_reason: null
  }, 201);
  const toggleSourceResponse = createDeferredResponse({
    ...initialSources[0],
    active: false
  });
  const syncResponse = createDeferredResponse({ processed_source_ids: [1, 2] });
  const reloadAfterSyncResponse = createDeferredResponse(initialSources);

  let sourcesGetCount = 0;
  let sourcesPostCalled = false;
  let sourcesPatchCalled = false;
  let sourcesSyncCalled = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/sources/sync" && method === "POST") {
      sourcesSyncCalled = true;
      return syncResponse.promise;
    }
    if (urlStr.match(/\/api\/sources\/\d+/) && method === "PATCH") {
      sourcesPatchCalled = true;
      return toggleSourceResponse.promise;
    }
    if (urlStr === "/api/sources" && method === "POST") {
      sourcesPostCalled = true;
      return addSourceResponse.promise;
    }
    if (urlStr === "/api/sources" && method === "GET") {
      sourcesGetCount++;
      if (sourcesSyncCalled) return reloadAfterSyncResponse.promise;
      return Promise.resolve(new Response(JSON.stringify(initialSources), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  expect(await screen.findByText("Alpha")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Source URL"), {
    target: { value: "example.com" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Add source" }));

  expect(screen.getByRole("button", { name: "Adding source..." })).toBeDisabled();

  addSourceResponse.resolve();

  expect(await screen.findByText("Example")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Disable Alpha" }));

  expect(screen.getByRole("button", { name: "Disable Alpha" })).toBeDisabled();

  toggleSourceResponse.resolve();

  await screen.findByRole("button", { name: "Enable Alpha" });

  fireEvent.click(screen.getByRole("button", { name: "Sync sources now" }));

  expect(screen.getByRole("button", { name: "Syncing sources..." })).toBeDisabled();

  syncResponse.resolve();
  reloadAfterSyncResponse.resolve();

  expect(await screen.findByText("Sync complete for 2 sources.")).toBeInTheDocument();
});

test("sources page reloads recent posts only after a destructive confirmation warning", async () => {
  const initialSource = {
    ...initialSources[0],
    post_count: 3
  };
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/sources" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify([initialSource]), { status: 200 }));
    }
    if (urlStr === "/api/sources/1/reload-posts" && method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ deleted: 2, reloaded: 3 }), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Sources" }));
  expect(await screen.findByText("Alpha")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Reload posts for Alpha" }));

  expect(confirmSpy).toHaveBeenCalledWith(
    "Reload posts for Alpha?\n\nThis will delete and reload posts from the last 2 months for this source. Post age is determined by published date when available, otherwise by the date the post was added."
  );
  expect(await screen.findByText("Deleted 2 recent posts. Reloaded 3 posts from the source.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/sources/1/reload-posts", { method: "POST" });
});
