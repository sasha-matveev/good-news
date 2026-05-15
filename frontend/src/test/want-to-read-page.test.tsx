import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

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

const savedPost = {
  id: 7,
  source_id: 3,
  source_name: "Gamma",
  canonical_url: "https://gamma.example/posts/saved",
  title: "Saved post",
  published_at: "2026-04-22T11:00:00Z",
  raw_content: "Worth reading later.",
  feedback_state: null,
  read_later: true,
  summary_ru: null,
  verdict: null,
  verdict_reason: null,
  ranking_explanation: "feedback=none"
};

test("want to read tab loads saved posts from the saved filter", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("window=all")) {
      return Promise.resolve(new Response(JSON.stringify([savedPost]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Want To Read" }));

  expect(await screen.findByText("Saved post")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Remove from want to read" })).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?sort=match", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=all", { method: "GET" });
  });
});

test("want to read tab shows an empty state when nothing is saved", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Want To Read" }));

  expect(await screen.findByText("No saved posts yet.")).toBeInTheDocument();
});

test("feed save flows through to the want to read tab", async () => {
  const newerPost = {
    id: 2,
    source_id: 2,
    source_name: "Beta",
    canonical_url: "https://beta.example/posts/newer",
    title: "Newer",
    published_at: "2026-04-20T09:00:00Z",
    raw_content: "Fresh enough for the default window.",
    feedback_state: null,
    read_later: false,
    summary_ru: null,
    verdict: null,
    verdict_reason: null,
    ranking_explanation: "feedback=none"
  };

  const newerPostSaved = { ...newerPost, read_later: true };

  let readLaterSaved = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts/2/read-later") && method === "POST") {
      readLaterSaved = true;
      return Promise.resolve(
        new Response(JSON.stringify({ post_id: 2, read_later: true }), { status: 200 })
      );
    }
    if (urlStr.includes("window=all")) {
      return Promise.resolve(
        new Response(JSON.stringify([newerPostSaved]), { status: 200 })
      );
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([newerPost]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("Newer")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Add to Read Later" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts/2/read-later", {
      body: JSON.stringify({ saved: true }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });

  fireEvent.click(screen.getByRole("button", { name: "Want To Read" }));

  expect(await screen.findByText("Newer")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Remove from want to read" })).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?sort=match", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=all", { method: "GET" });
  });
});

test("want to read page can remove a saved post without touching other tabs", async () => {
  let readLaterRemoved = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts/7/read-later") && method === "POST") {
      readLaterRemoved = true;
      return Promise.resolve(
        new Response(JSON.stringify({ post_id: 7, read_later: false }), { status: 200 })
      );
    }
    if (urlStr.includes("window=all")) {
      return Promise.resolve(new Response(JSON.stringify([savedPost]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Want To Read" }));

  expect(await screen.findByText("Saved post")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Remove from want to read" }));

  expect(await screen.findByText("No saved posts yet.")).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts/7/read-later", {
      body: JSON.stringify({ saved: false }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });
});

test("want to read page shows an active saving state while removing a saved post", async () => {
  const removeResponse = createDeferredResponse({
    post_id: 7,
    read_later: false
  });

  let removeCalled = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts/7/read-later") && method === "POST") {
      removeCalled = true;
      return removeResponse.promise;
    }
    if (urlStr.includes("window=all")) {
      return Promise.resolve(new Response(JSON.stringify([savedPost]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Want To Read" }));

  expect(await screen.findByText("Saved post")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Remove from want to read" }));

  expect(screen.getByRole("button", { name: "Removing..." })).toBeDisabled();

  removeResponse.resolve();

  expect(await screen.findByText("No saved posts yet.")).toBeInTheDocument();
});
