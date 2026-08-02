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

const initialSettings = {
  daily_digest_time: "12:00",
  weekly_digest_day_of_week: "mon",
  weekly_digest_time: "18:30",
  recipient_email: "reader@example.com",
  sender_identity: "Good News Digest <digest@example.com>",
  smtp_host: "smtp.example.com",
  smtp_port: 587,
  smtp_username: "digest-user",
  smtp_security_mode: "starttls",
  daily_digest_enabled: true,
  daily_digest_catch_up_enabled: true,
  weekly_digest_enabled: false,
  weekly_digest_catch_up_enabled: true,
  smtp_password_configured: true,
  analysis_summary_prompt: "Default summary instructions.",
  analysis_verdict_reason_prompt: "Default verdict instructions."
};

const savedSettings = {
  daily_digest_time: "08:45",
  weekly_digest_day_of_week: "fri",
  weekly_digest_time: "16:30",
  recipient_email: "reader@example.com",
  sender_identity: "Good News Digest <digest@example.com>",
  smtp_host: "smtp.example.com",
  smtp_port: 465,
  smtp_username: "digest-user",
  smtp_security_mode: "ssl",
  daily_digest_enabled: true,
  daily_digest_catch_up_enabled: false,
  weekly_digest_enabled: true,
  weekly_digest_catch_up_enabled: false,
  smtp_password_configured: true,
  analysis_summary_prompt: "Default summary instructions.",
  analysis_verdict_reason_prompt: "Default verdict instructions."
};

test("settings page loads persisted settings, supports masked password replacement, saves schedule, and sends test email", async () => {
  let settingsPutCalled = false;
  let testEmailCalled = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/settings/test-email" && method === "POST") {
      testEmailCalled = true;
      return Promise.resolve(new Response(JSON.stringify({ status: "sent" }), { status: 200 }));
    }
    if (urlStr === "/api/settings" && method === "PUT") {
      settingsPutCalled = true;
      return Promise.resolve(new Response(JSON.stringify(savedSettings), { status: 200 }));
    }
    if (urlStr === "/api/settings" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(initialSettings), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Settings" }));

  expect(await screen.findByDisplayValue("12:00")).toBeInTheDocument();
  expect(screen.getByDisplayValue("18:30")).toBeInTheDocument();
  expect(screen.getByDisplayValue("reader@example.com")).toBeInTheDocument();
  expect(screen.getByLabelText("Weekly digest day of week")).toHaveValue("mon");
  expect(screen.getByLabelText("Enable weekly digest")).not.toBeChecked();
  expect(screen.getByText("SMTP password configured")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Daily digest time"), {
    target: { value: "08:45" }
  });
  fireEvent.change(screen.getByLabelText("Weekly digest day of week"), {
    target: { value: "fri" }
  });
  fireEvent.change(screen.getByLabelText("Weekly digest time"), {
    target: { value: "16:30" }
  });
  fireEvent.change(screen.getByLabelText("SMTP port"), {
    target: { value: "465" }
  });
  fireEvent.change(screen.getByLabelText("Security mode"), {
    target: { value: "ssl" }
  });
  fireEvent.click(screen.getByLabelText("Replace SMTP password"));
  fireEvent.change(screen.getByLabelText("New SMTP password"), {
    target: { value: "fresh-secret" }
  });
  fireEvent.click(screen.getByLabelText("Disable startup catch-up"));
  fireEvent.click(screen.getByLabelText("Enable weekly digest"));
  fireEvent.click(screen.getByLabelText("Disable weekly startup catch-up"));
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

  expect(await screen.findByText("Settings saved.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Send test email" }));

  expect(await screen.findByText("Test email sent.")).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/posts?window=last_month&sort=date&limit=50", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/settings", { method: "GET" });
    expect(fetchMock).toHaveBeenCalledWith("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        daily_digest_time: "08:45",
        weekly_digest_day_of_week: "fri",
        weekly_digest_time: "16:30",
        recipient_email: "reader@example.com",
        sender_identity: "Good News Digest <digest@example.com>",
        smtp_host: "smtp.example.com",
        smtp_port: 465,
        smtp_username: "digest-user",
        smtp_security_mode: "ssl",
        daily_digest_enabled: true,
        daily_digest_catch_up_enabled: false,
        weekly_digest_enabled: true,
        weekly_digest_catch_up_enabled: false,
        analysis_summary_prompt: "Default summary instructions.",
        analysis_verdict_reason_prompt: "Default verdict instructions.",
        smtp_password: "fresh-secret"
      })
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/test-email", {
      method: "POST"
    });
  });
});

test("settings page shows active button labels while saving settings and sending a test email", async () => {
  const saveResponse = createDeferredResponse(initialSettings);
  const testEmailResponse = createDeferredResponse({ status: "sent" });

  let settingsPutCalled = false;
  let testEmailCalled = false;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/settings/test-email" && method === "POST") {
      testEmailCalled = true;
      return testEmailResponse.promise;
    }
    if (urlStr === "/api/settings" && method === "PUT") {
      settingsPutCalled = true;
      return saveResponse.promise;
    }
    if (urlStr === "/api/settings" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(initialSettings), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Settings" }));

  expect(await screen.findByDisplayValue("12:00")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

  expect(screen.getByRole("button", { name: "Saving settings..." })).toBeDisabled();

  saveResponse.resolve();

  expect(await screen.findByText("Settings saved.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Send test email" }));

  expect(screen.getByRole("button", { name: "Sending test email..." })).toBeDisabled();

  testEmailResponse.resolve();

  expect(await screen.findByText("Test email sent.")).toBeInTheDocument();
});

test("settings page exposes AI analysis prompt editors and sends the edited summary prompt on save", async () => {
  let putBody: unknown = null;

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((url, init) => {
    const urlStr = typeof url === "string" ? url : String(url);
    const method = (init as RequestInit | undefined)?.method ?? "GET";

    if (urlStr.includes("/api/monitoring/summary")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr.includes("/api/posts")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (urlStr === "/api/settings" && method === "PUT") {
      putBody = JSON.parse((init as RequestInit).body as string);
      return Promise.resolve(new Response(JSON.stringify(savedSettings), { status: 200 }));
    }
    if (urlStr === "/api/settings" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(initialSettings), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<AppShell />);

  fireEvent.click(screen.getByRole("button", { name: "Settings" }));

  // Both editor controls render and are pre-filled from the loaded settings.
  const summaryEditor = await screen.findByLabelText("Post summary prompt");
  expect(summaryEditor).toBeInTheDocument();
  expect(screen.getByLabelText("Verdict reason prompt")).toBeInTheDocument();
  expect(summaryEditor).toHaveValue("Default summary instructions.");

  // Edit the summary prompt with Markdown, then verify the Preview toggle renders it.
  fireEvent.change(summaryEditor, { target: { value: "# My heading\n\nSummarize **clearly**." } });

  // The Post summary editor's own Edit/Preview tabs are the first pair on the page.
  const previewButtons = screen.getAllByRole("tab", { name: "Preview" });
  fireEvent.click(previewButtons[0]);

  const heading = await screen.findByRole("heading", { name: "My heading" });
  expect(heading).toBeInTheDocument();
  expect(heading.tagName).toBe("H1");
  expect(screen.getByText("clearly")).toBeInTheDocument();

  // Switch back to Edit and save; the PUT carries the edited prompt text.
  fireEvent.click(screen.getAllByRole("tab", { name: "Edit" })[0]);
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

  await waitFor(() => {
    expect(putBody).toMatchObject({
      analysis_summary_prompt: "# My heading\n\nSummarize **clearly**.",
      analysis_verdict_reason_prompt: "Default verdict instructions."
    });
  });
});
