# PR-19 production strangler foundation

## Ownership and rollback

`frontend/src/lib/api.ts` is the browser routing control plane. At PR-19 close,
every exported API operation is explicitly owned by `python`. Production builds
ignore `VITE_API_BACKEND_OVERRIDE`; local, preview, staging, development, and
test builds may use it as a whole-application diagnostic override.

The behavior-preserving rollback is to restore the previous single-origin
`apiFetch` implementation or revert the frontend artifact. It requires no
database migration or backend deployment because the operation map still sends
all production calls to `VITE_CONTENT_API_ORIGIN`.

## Shadow-readiness gates

- Python and Java identify responses and preserve or generate correlation IDs.
- Both origins permit the production frontend's authenticated browser requests
  and preflight headers.
- Java `/api/health` checks database connectivity and the minimum shared schema,
  returning the same healthy body as Python and a bounded `503` failure body.
- PostgreSQL pool acquisition, connection creation, statements, idle lifetime,
  and maximum lifetime are bounded; SMTP connect/read/write calls are bounded.
- With current single-instance caps, Python's maximum pool allocation (`15`) and
  Java's (`5`) consume at most `20` application connections before the Neon
  migration/operator reserve.

## Deployment handoff

The later shadow-deployment PR must apply the Java Cloud Run JVM baseline and
explicit request concurrency described in `backend-java/README.md`, configure
`GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN`, preserve `max-instances=1`, and confirm the
active Neon connection limit before deployment. PR-19 itself changes neither
production ownership nor Cloud Scheduler targets.
