import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

test("preference profile page loads aggregate explanations from the API", async () => {
  const preferencesData = {
    summary:
      "From 4 feedback signals, the profile is learning toward observability postmortems from Alpha and away from opinion pieces.",
    positive_signals: [
      "2 positive signals for source Alpha",
      "2 positive signals for topic observability",
    ],
    negative_signals: ["1 not-interesting signal against format opinion"],
    learning_proof: [
      "4 feedback decisions recorded: 2 interesting, 1 want to read, 1 not interesting.",
      "Strongest positive pull: source Alpha and topic observability.",
    ],
    feedback_totals: {
      interesting: 2,
      want_to_read: 1,
      not_interesting: 1,
      total: 4,
    },
  };

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/preferences")) {
      return Promise.resolve(new Response(JSON.stringify(preferencesData), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Preference Profile" }));

  expect(
    await screen.findByText(
      "From 4 feedback signals, the profile is learning toward observability postmortems from Alpha and away from opinion pieces."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("2 positive signals for source Alpha")).toBeInTheDocument();
  expect(screen.getByText("1 not-interesting signal against format opinion")).toBeInTheDocument();
  expect(screen.getByText("Learning proof")).toBeInTheDocument();
  expect(
    screen.getByText("4 feedback decisions recorded: 2 interesting, 1 want to read, 1 not interesting.")
  ).toBeInTheDocument();
  expect(screen.getByText("Interesting: 2")).toBeInTheDocument();
  expect(screen.getByText("Want to read: 1")).toBeInTheDocument();
  expect(screen.getByText("Not interesting: 1")).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=all&sort=match&limit=50", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/preferences", { method: "GET" });
  });
});
