# Frontend Tests

## Install dependencies

Run this once after cloning the repo or after dependency changes:

```bash
npm install
```

## Run the full frontend test suite

From the `frontend` directory:

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

## Why `npm test run` is wrong here

`npm test run` appends `run` to the existing test command, so npm executes:

```bash
vitest run run
```

That second `run` becomes a Vitest filter instead of a command, which is why Vitest reports that it cannot find matching test files.
