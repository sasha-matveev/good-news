import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";

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

test("digests page renders mixed daily and weekly history entries and opens weekly digest detail", async () => {
  const digestsResponse = createDeferredResponse([
    {
      id: 22,
      digest_type: "weekly",
      status: "sent",
      sent_at: "2026-04-27T16:30:00Z",
      included_post_count: 1
    },
    {
      id: 21,
      digest_type: "daily",
      status: "sent",
      sent_at: "2026-04-26T12:05:00Z",
      included_post_count: 2
    }
  ]);

  const digestDetail = {
    id: 22,
    digest_type: "weekly",
    status: "sent",
    sent_at: "2026-04-27T16:30:00Z",
    title: "Good News weekly digest for 2026-04-27",
    included_posts: [
      { post_id: 3, title: "Weekly Post", feedback_state: "interesting" }
    ],
    rendered_html:
      "<html><body><h1>Good News weekly digest for 2026-04-27</h1><p>Digest body</p></body></html>"
  };

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/digests/22") {
      return Promise.resolve(new Response(JSON.stringify(digestDetail), { status: 200 }));
    }
    if (urlStr === "/api/digests") {
      return digestsResponse.promise;
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Digests" }));

  expect(screen.getByText("Loading digests...")).toBeInTheDocument();

  digestsResponse.resolve();

  const weeklyDigestRow = await screen.findByRole("button", {
    name: /2026-04-27 16:30 UTC/i
  });
  expect(within(weeklyDigestRow).getByText("Type: Weekly digest")).toBeInTheDocument();
  expect(within(weeklyDigestRow).getByText("Included posts: 1")).toBeInTheDocument();

  const dailyDigestRow = screen.getByRole("button", {
    name: /2026-04-26 12:05 UTC/i
  });
  expect(within(dailyDigestRow).getByText("Type: Daily digest")).toBeInTheDocument();
  expect(within(dailyDigestRow).getByText("Included posts: 2")).toBeInTheDocument();

  fireEvent.click(weeklyDigestRow);

  expect(await screen.findByText("Good News weekly digest for 2026-04-27")).toBeInTheDocument();
  expect(screen.getByText("Weekly Post (interesting)")).toBeInTheDocument();
  expect(screen.getByText("Stored web version")).toBeInTheDocument();
  expect(screen.getAllByText("Type: Weekly digest")).toHaveLength(2);
  expect(screen.getByText("Sent: 2026-04-27 16:30 UTC")).toBeInTheDocument();
  expect(screen.getByTitle("Rendered digest HTML web version")).toHaveAttribute(
    "srcdoc",
    "<html><body><h1>Good News weekly digest for 2026-04-27</h1><p>Digest body</p></body></html>"
  );

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=last_month&sort=date&limit=50", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/digests", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/digests/22", { method: "GET" });
  });
});

test("digests page shows an empty state when no persisted digests exist yet", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/digests") {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Digests" }));

  expect(await screen.findByText("No sent digests exist yet.")).toBeInTheDocument();
  expect(screen.getByText("Sent digest history will appear here after the first delivery.")).toBeInTheDocument();
});

test("digests page shows an error state when digest history cannot be loaded", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/digests") {
      return Promise.resolve(new Response("boom", { status: 500 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Digests" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Request failed with status 500");
  expect(screen.getByText("Sent digest history is unavailable right now.")).toBeInTheDocument();
});
