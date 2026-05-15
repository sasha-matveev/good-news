// @vitest-environment node

import { readFile } from "node:fs/promises";

import { expect, test } from "vitest";

test("frontend index.html mounts the app entrypoint", async () => {
  const html = await readFile(new URL("../../index.html", import.meta.url), "utf8");

  expect(html).toContain('<div id="root"></div>');
  expect(html).toContain('<script type="module" src="/src/main.tsx"></script>');
});
