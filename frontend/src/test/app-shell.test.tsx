import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

test("renders the approved shell navigation and header summary skeleton", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200
      })
    )
  );

  render(<AppShell />);

  const nav = screen.getByRole("navigation", { name: "Primary navigation" });
  const navButtons = within(nav).getAllByRole("button");
  expect(navButtons).toHaveLength(7);
  expect(navButtons.map((b) => b.textContent)).toEqual([
    "Feed",
    "Want To Read",
    "Preference Profile",
    "Sources",
    "Digests",
    "Settings",
    "Monitoring"
  ]);

  for (const label of ["Tracked sources", "System", "Last Sync"]) {
    expect(screen.getByText(label)).toBeInTheDocument();
  }

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();
});

test("app shell lands directly on want to read for deep-link paths", async () => {
  const emptyResponse = () => new Response(JSON.stringify([]), { status: 200 });
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockImplementation((url) => {
      if (typeof url === "string" && url.includes("read_later=true")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
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
                relevance_score: null,
                ranking_explanation: "feedback=none"
              }
            ]),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(emptyResponse());
    });

  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState({}, "", "/want-to-read");

  render(<AppShell />);

  expect(await screen.findByText("Saved post")).toBeInTheDocument();
  expect(window.location.pathname).toBe("/want-to-read");

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/posts?window=all&read_later=true",
      { method: "GET" }
    );
  });

  fireEvent.click(screen.getByRole("button", { name: "Feed" }));

  expect(await screen.findByText("No collected posts yet.")).toBeInTheDocument();
  expect(window.location.pathname).toBe("/feed");
});

test("app shell constrains the main content column so long page content cannot widen the layout", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200
      })
    )
  );

  const { container } = render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  await screen.findByText("No sources yet.");

  const nav = screen.getByRole("navigation", { name: "Primary navigation" });
  const shellGrid = nav.parentElement;
  const contentColumn = nav.nextElementSibling;

  expect(shellGrid).toHaveStyle({ gridTemplateColumns: "220px minmax(0, 1fr)" });
  expect(contentColumn).toHaveStyle({ minWidth: "0" });
});
