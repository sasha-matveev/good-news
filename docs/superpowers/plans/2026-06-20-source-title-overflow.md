# Source Title Overflow Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep source-card action buttons visible when a source has a very long name or URL by truncating the identity text within the available header width.

**Architecture:** Limit the change to the Sources page card header. Express the layout contract through the existing inline styles: the identity group takes the remaining width and clips overflow, its text and URL can shrink and ellipsize, and the action group remains non-shrinking.

**Tech Stack:** React 18, TypeScript, Vitest, Testing Library, inline CSS styles

---

### Task 1: Constrain source identity text without moving actions

**Files:**
- Modify: `frontend/src/test/sources-page.test.tsx`
- Modify: `frontend/src/pages/SourcesPage.tsx:413-434`

- [ ] **Step 1: Write the failing regression test**

Append a focused test that returns a source with a long name and URL, opens the Sources page, and asserts the card-header layout contract:

```tsx
test("long source identity is constrained so actions remain visible", async () => {
  const longName = "Engineering at Slack — Hear directly from Slack's engineers about what we build, why and how we build it, repeated for overflow";
  const longUrl = "https://example.com/a/very/long/source/url/that/must/not/expand/the/source/card/header/beyond/the/viewport";
  const source = { ...initialSources[0], display_name: longName, original_url: longUrl };

  vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockImplementation((url) => {
    const urlStr = typeof url === "string" ? url : String(url);
    if (urlStr === "/api/sources") {
      return Promise.resolve(new Response(JSON.stringify([source]), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  }));

  render(<AppShell />);
  fireEvent.click(screen.getByRole("button", { name: "Sources" }));

  const title = await screen.findByRole("heading", { name: longName });
  const textContainer = title.parentElement;
  const identityGroup = textContainer?.parentElement;
  const sourceUrl = screen.getByRole("link", { name: longUrl });
  const actionGroup = screen.getByRole("button", { name: `Sync ${longName}` }).parentElement;

  expect(identityGroup).toHaveStyle({ flex: "1 1 0", minWidth: "0", overflow: "hidden" });
  expect(textContainer).toHaveStyle({ flex: "1 1 0", minWidth: "0", overflow: "hidden" });
  expect(sourceUrl).toHaveStyle({ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
  expect(actionGroup).toHaveStyle({ flexShrink: "0" });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run src/test/sources-page.test.tsx` from `frontend`.

Expected: the new test fails because the identity group lacks `flex: 1 1 0` and overflow constraints, and the URL lacks ellipsis styles.

- [ ] **Step 3: Add the minimal layout constraints**

Update the source-card header identity markup in `SourcesPage.tsx`:

```tsx
<div style={{ display: "flex", flex: "1 1 0", gap: "12px", alignItems: "center", minWidth: 0, overflow: "hidden" }}>
  <SourceIcon url={source.original_url} size={24} title={sourceTitle(source)} />
  <div style={{ flex: "1 1 0", minWidth: 0, overflow: "hidden" }}>
    <h3 style={{ fontSize: "18px", margin: "0 0 3px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      {sourceTitle(source)}
    </h3>
    <a
      href={source.original_url}
      target="_blank"
      rel="noreferrer"
      style={{ color: theme.color.muted, display: "block", fontSize: "12px", overflow: "hidden", textDecoration: "none", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
    >
      {source.original_url}
    </a>
  </div>
</div>
```

Keep the existing action-group `flexShrink: 0` rule unchanged.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- --run src/test/sources-page.test.tsx` from `frontend`.

Expected: all Sources page tests pass.

- [ ] **Step 5: Run full frontend verification**

Run from `frontend`:

```powershell
npm test
npm run build
```

Expected: both commands exit successfully with no test failures or TypeScript/build errors.

- [ ] **Step 6: Verify visually at a constrained viewport**

Open the Sources page with the long-name fixture at a viewport comparable to the reported screenshot. Confirm that the title and URL truncate, all action buttons remain inside the card, and `document.documentElement.scrollWidth` does not exceed `document.documentElement.clientWidth` because of the source card.

- [ ] **Step 7: Commit the implementation**

```powershell
git add frontend/src/pages/SourcesPage.tsx frontend/src/test/sources-page.test.tsx docs/superpowers/plans/2026-06-20-source-title-overflow.md
git commit -m "fix: keep source actions visible for long titles"
```
