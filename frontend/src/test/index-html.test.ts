// @vitest-environment node

import { readFile } from "node:fs/promises";

import { expect, test } from "vitest";

test("frontend index.html mounts the app entrypoint", async () => {
  const html = await readFile(new URL("../../index.html", import.meta.url), "utf8");

  expect(html).toContain('<div id="root"></div>');
  expect(html).toContain('<script type="module" src="/src/main.tsx"></script>');
});

test("frontend index.html links the favicon asset", async () => {
  const html = await readFile(new URL("../../index.html", import.meta.url), "utf8");
  const favicon = await readFile(new URL("../../public/favicon.svg", import.meta.url), "utf8");

  expect(html).toContain('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />');
  expect(favicon).toContain('viewBox="0 0 64 64"');
});
