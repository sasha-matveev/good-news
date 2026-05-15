import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppShell } from "../app/AppShell";

beforeEach(() => {
  window.history.replaceState({}, "", "/feed");
});

test("monitoring page renders operator sections and open grafana link", async () => {
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Monitoring" }));

  expect(await screen.findByRole("heading", { name: "Source health" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "System health" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "LLM queue" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Capacity" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Grafana" })).toHaveAttribute(
    "href",
    "http://127.0.0.1:3000/d/good-news-overview/good-news-observability-overview"
  );
});

test("monitoring page shows real metrics when backend returns data", async () => {
  const summaryData = {
    sources_active: 2,
    sources_total: 3,
    posts_total: 15,
    posts_unranked: 4,
    last_sync_at: "2026-05-15T10:00:00Z",
    services: {
      content_api: "ok",
      analysis_llm: "ok",
      source_ingestion: "error",
      delivery: "ok"
    }
  };

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url) => {
    if (typeof url === "string" && url.includes("/api/monitoring/summary")) {
      return Promise.resolve(
        new Response(JSON.stringify(summaryData), { status: 200 })
      );
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Monitoring" }));

  await screen.findByRole("heading", { name: "Source health" });
  await waitFor(() => {
    expect(screen.getAllByText("2026-05-15").length).toBeGreaterThanOrEqual(1);
  });
  expect(screen.getByText("4")).toBeInTheDocument();
  expect(screen.getAllByText("OK").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("Error")).toBeInTheDocument();
});

test("monitoring page shows dashes when backend returns empty array", async () => {
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Monitoring" }));

  await screen.findByRole("heading", { name: "Source health" });
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});
