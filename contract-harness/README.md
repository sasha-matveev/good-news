# Differential backend contract harness

The harness compares Python and Java at the observable boundaries used for
production ownership decisions:

- HTTP status, error class, JSON shape/value, ordering, redirects, and URLs;
- independently seeded PostgreSQL state after every mutating scenario;
- SMTP, Gemini, and source-fetch events captured by the shared fake-boundary
  service;
- a route-group parity report whose final line is the go/no-go decision.

Mutating scenarios never run sequentially against one database. Python uses
`postgres-python`; Java uses `postgres-java`. The seed is applied afresh to both
before each scenario. The smaller read-only mode is the only mode allowed to
use one shared database and rejects non-safe HTTP methods.

## Run locally

Docker, Python 3.12, and Java 21 are required:

```sh
./contract-harness/run-local.sh
./contract-harness/run-read-only.sh
```

Run just the reaction slice while diagnosing a drift:

```sh
good-news-contract --mode differential --scenario feedback-idempotent
```

Every mismatch identifies the scenario and exact response, side-effect, table,
row, or field path, for example:

```text
feedback-idempotent contract mismatch:
  $.tables.feedback[0].state: python='interesting', java='not_interesting'
```

## Volatile values

Normalization is intentionally allowlist-only. The current documented volatile
field names are generated `id`, `created_at`, `updated_at`, `sent_at`, and
`correlation_id`. Do not add a field merely to make a drift green: explain why
it is nondeterministic and why its value is not part of the public or persisted
contract.

The fixtures use the same public origins, deterministic analysis/source
responses, and explicit timestamps. Mutation snapshots still normalize
database-generated timestamps.

Columns named `*_json` are decoded before comparison. This is structural
comparison rather than value normalization: object keys and values remain
strict, while insignificant JSON whitespace and object-key ordering do not
create false mismatches.

## Adding a route

Add a scenario to `scenarios.json`, including every table it may change.
Adding a normal route does not require changes to orchestration or comparison.
Every active route group must retain at least one differential scenario before
the report can return `GO`.

Authentication integration tests in each backend remain responsible for
cryptographic token verification. Differential auth processes use a
deterministic token adapter; they compare missing tokens, allowlisted and
rejected email claims, scheduler OIDC, and CORS without contacting Firebase or
Google.

Fixed time, deterministic authentication, source responses, and analysis
responses are contract-harness adapters, not production features. The Python
adapter is copied only by `contract-harness/Dockerfile.python`. The Java
adapter sources are copied into the application source tree only inside the
build stage of `contract-harness/Dockerfile.java`. The production Dockerfiles
do not contain either adapter.

The boundary service records SMTP envelopes, Gemini requests, and source-fetch
requests. The runner clears it before each backend observation and includes the
ordered event list in contract equality, so a retry or duplicate side effect is
reported at its exact list position.
