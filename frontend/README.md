# Frontend Tests

Run the commands below from the `frontend` directory.

This frontend now requires Node `^20.19.0 || >=22.12.0`.

## Install dependencies

For a clean install that matches `package-lock.json`:

```bash
npm ci
```

Use `npm install` only when you intentionally update dependencies and need to refresh `package-lock.json`.

## Run the full frontend test suite

After dependencies are installed:

```bash
npm test
```

This runs the `test` script from `package.json`, which is currently:

```bash
vitest run
```

## Run a single test file

Pass the file path to Vitest after `--`:

```bash
npm test -- --run src/test/feed-page.test.tsx
```

You can do the same for any other test file under `src/test/`.
