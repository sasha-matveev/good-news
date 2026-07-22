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

## Backend operation routing

`src/lib/api.ts` is the only browser API ownership control plane. Every
exported API operation has an explicit `python` or `java` owner, and tests fail
when a newly exported operation is missing from the map. Production currently
keeps every operation on Python.

- `VITE_CONTENT_API_ORIGIN` is the Python service origin.
- `VITE_JAVA_API_ORIGIN` is the Java service origin.
- `VITE_DEPLOY_ENV` must be `production` for production builds.
- `VITE_API_BACKEND_OVERRIDE=python|java` is honored only when
  `VITE_DEPLOY_ENV` is `local`, `preview`, or `staging` (and in development or
  test mode). It is ignored in production.

The override is a whole-app diagnostic aid, not a production feature flag.
