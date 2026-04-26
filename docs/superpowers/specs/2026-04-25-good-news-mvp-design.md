# Good News MVP Design

## Status

Draft approved in conversation, pending user review of this written spec.

## Working Model

Development follows an agile process.

The customer may request changes to the specification and the program during later implementation stages or during actual use of the system. Change requests are handled through the project lead, who decides how to decompose the request and which agents should execute analysis, specification updates, implementation, testing, and operational changes.

This means:
- the current spec defines the first implementation phase, not the final product;
- later phases may revise data model details, UI behavior, integrations, ranking rules, and operational setup;
- the system should be designed for controlled evolution rather than hard-coded one-off behavior.

## Goal

Build a single-user local-first system that aggregates technical blog posts, generates Russian summaries with a local AI model, ranks posts by learned user preferences, sends scheduled email digests, and provides a polished web UI for managing sources, reviewing posts, and inspecting digest history.

## Scope Of Phase 1

Phase 1 includes:
- text blogs only;
- automatic daily and weekly digests;
- a separate daily evening observability email with Grafana screenshot and error summary;
- source management through the site;
- local AI through a locally running model;
- preference learning from explicit user actions;
- fallback parsing for sites without a usable RSS or Atom feed;
- operational observability using ready-made products rather than a custom monitoring UI.

Phase 1 excludes:
- video platforms;
- full article rendering inside the site;
- multi-user support, roles, or account management;
- vector search and embedding-based ranking;
- full cloud deployment;
- enterprise auth flows.

## Product Behavior

### Core User Flows

1. The user adds a blog by plain site URL through the web UI.
2. The system tries to discover RSS or Atom feeds.
3. If feed discovery fails or is incomplete, the system uses HTML parsing with AI-assisted fallback extraction.
4. The scheduler periodically ingests new posts from all active sources.
5. The AI pipeline creates a Russian summary, classifies post characteristics, produces a short verdict with a reason, and contributes to ranking.
6. The digest generator sends a daily digest at midday and a weekly digest on the night from Saturday to Sunday, both configurable through the UI.
7. If the system was offline during a planned send, the next startup sends the latest missed daily digest and the latest missed weekly digest independently.
8. The user clicks links in the email to mark a post as `interesting`, `not interesting`, or `want to read`.
9. The feedback is stored and used to update preference scoring.
10. The site shows the latest month of posts, the read-later list, source management, settings, digest history, and a preference explanation page.

### Digest Rules

- Every source publication is considered for the digest if it falls into the digest window.
- Posts are sorted by estimated user interest.
- The email shows the top 5 posts.
- If more than 5 posts exist, the email adds a line in the form `more X less interesting posts`.
- The site always allows viewing the full set of collected posts.

### Digest Content Per Post

Each digest entry contains:
- post title;
- source name;
- source link to original post;
- Russian AI summary;
- short verdict with a reason explaining why the post is likely interesting or not interesting;
- direct action links for `Interesting`, `Not Interesting`, and `Want To Read`.

### Preferences

The first phase uses a hybrid ranking approach:
- explicit user feedback is the strongest signal;
- source affinity contributes to ranking;
- topic affinity contributes to ranking;
- practical engineering material is preferred over corporate or marketing-heavy material;
- post format matters, for example tutorial, case study, postmortem, release note, announcement, opinion;
- technical depth matters;
- the AI model explains and summarizes, but does not act as the only ranking mechanism.

No vector database is required in phase 1.

## UI Design

### Visual Direction

The site uses:
- a light theme;
- restrained IDE-inspired visual language;
- panel-based layout, clear tabs, and status-like UI elements;
- selective monospace use for metadata only;
- normal highly readable typography for titles and body text;
- no exaggerated faux-code-editor styling.

The UI must feel like a polished product, not an admin scaffold.

### Screens

Phase 1 includes these screens:

1. Feed
- all posts from the last month;
- ranking-based default ordering;
- filters by source and user feedback state;
- summary, verdict, reason, metadata, and original link.

2. Want To Read
- only posts marked for later reading.

3. Digests
- digest history;
- daily and weekly digest records;
- sent time, type, included posts, and web version of the sent digest.

4. Sources
- list of configured blogs;
- add by plain URL;
- enable and disable source;
- source status;
- last successful sync;
- indication that re-adaptation is needed.

5. Settings
- digest schedule;
- recipient email;
- sender email settings;
- SMTP settings;
- write-only password replacement;
- test email trigger.

6. Preference Profile
- explanation of what kinds of posts are currently preferred;
- explanation of what tends to be marked as not interesting.

Observability lives in Grafana rather than in a custom product screen.

## Architecture

### Main Stack

- Backend: Python + FastAPI
- Frontend: React + Vite
- Database: PostgreSQL
- Scheduler: APScheduler inside backend service
- Local AI runtime: Ollama
- Email transport: Gmail SMTP using a dedicated sender account and app password
- Observability: Grafana OSS + Prometheus + Loki + OpenTelemetry Collector + grafana-image-renderer
- Local orchestration: Docker Compose

### Services

1. frontend
- React application for all end-user UI.

2. backend
- FastAPI application;
- owns API, scheduler startup, ingestion orchestration, AI orchestration, digest generation, settings management, and secret store integration.

3. postgres
- primary application database;
- stores product data and encrypted SMTP credentials.

4. ollama
- local model serving.

5. grafana
- dashboards, alerting, operations inspection.

6. prometheus
- metrics storage and scraping.

7. loki
- log storage.

8. otel-collector
- central telemetry ingestion and export.

9. grafana-image-renderer
- renders dashboard panels or dashboards to PNG for the evening observability email.

## Data Model

### sources

Stores:
- source id;
- display name;
- original URL entered by user;
- discovered feed URL if any;
- current ingestion strategy;
- active flag;
- status;
- last success time;
- last failure time;
- needs readaptation flag and reason.

### posts

Stores:
- post id;
- source id;
- canonical URL;
- title;
- published timestamp;
- raw excerpt or extracted content;
- content hash for deduplication;
- ingest metadata.

### post_analysis

Stores:
- post id;
- Russian summary;
- extracted topics;
- detected format;
- inferred technical depth;
- verdict;
- verdict reason;
- rule-based score;
- AI metadata versioning fields.

### feedback

Stores:
- feedback id;
- post id;
- action type: `interesting`, `not_interesting`, `want_to_read`;
- source of action: `site` or `email`;
- timestamp.

### digests

Stores:
- digest id;
- digest type: `daily`, `weekly`, `observability_daily`;
- time window start and end;
- send status;
- send time;
- rendered HTML;
- rendered summary metadata.

### digest_items

Stores:
- digest id;
- post id;
- rank position;
- inclusion reason.

### settings

Stores:
- daily digest time;
- weekly digest day and time;
- recipient email;
- sender email address;
- sender display name;
- SMTP host;
- SMTP port;
- SMTP username;
- SMTP security mode;
- flags for catch-up behavior.

### secret_settings

Stores encrypted secret values such as:
- SMTP password ciphertext;
- metadata such as last updated timestamp.

Write-only behavior is enforced at the API and UI layers.

### preference_profile

Stores aggregated signals such as:
- source preference weights;
- topic preference weights;
- format preference weights;
- technical-depth preference weights;
- explanations for positive and negative tendencies.

### technical_events

Stores:
- severity;
- subsystem;
- event code;
- human-readable summary;
- structured details;
- timestamps;
- related source, digest, or job references.

## Secret Management

### Product Secrets

User-managed email credentials are configured through the site.

Requirements:
- SMTP password is entered through the UI;
- SMTP password is never returned in plaintext;
- UI shows only configured state and replacement controls;
- SMTP password is stored encrypted in PostgreSQL.

Encryption design:
- backend encrypts SMTP password before persisting it;
- backend decrypts only when sending email or testing SMTP configuration;
- encryption uses a master key loaded from infrastructure secret storage.

### Infrastructure Secrets

Infrastructure secrets must not be stored inside the project folder.

For local operation, infrastructure secrets are stored in Windows Credential Manager.

These include:
- application master key for secret encryption;
- PostgreSQL application password.

The backend accesses them through a `SecretStore` abstraction.

The `SecretStore` interface is designed to be replaceable later for cloud deployment, for example with:
- Docker secrets;
- Kubernetes secrets;
- managed cloud secret stores.

This keeps business logic independent from the local storage mechanism.

Non-secret values such as database host or base URL may be stored in regular configuration.

## Ingestion And Parsing

### Source Onboarding

When a user adds a blog URL:
- the system normalizes the URL;
- tries feed discovery using standard techniques;
- stores the best discovered feed if found;
- if feed discovery fails, stores an HTML-based parsing strategy.

### Feed Discovery

The system first attempts deterministic discovery:
- RSS and Atom common paths;
- `link rel=\"alternate\"` tags;
- sitemap hints;
- common blog engine conventions.

### HTML Fallback

If standard feed discovery is insufficient:
- fetch source HTML;
- detect listing pages and article links;
- extract candidate article metadata;
- store the strategy used for future polling.

AI may assist with classification or extraction hints, but parsing should remain primarily deterministic and repeatable.

### Readaptation

If a source starts failing because page structure changed:
- mark source as requiring re-adaptation;
- emit technical events and alerts;
- run the same adaptation process used during source onboarding;
- save the new working parsing strategy if adaptation succeeds.

## AI Pipeline

### Local Model

The system uses a local model served via Ollama.

The model is used for:
- Russian summaries;
- post characteristic extraction support;
- verdict phrasing with a reason.

The model is not treated as long-term memory.

### Memory

User preference memory lives in PostgreSQL, not inside the model.

This includes:
- feedback history;
- digest history;
- aggregated preference profile;
- analysis artifacts used for ranking explanations.

### Ranking

Ranking combines:
- explicit user feedback;
- source affinity;
- topic affinity;
- material format;
- practical engineering orientation;
- estimated technical depth;
- recency where useful.

The LLM helps with explanation and content transformation, but ranking remains inspectable and controllable.

## Scheduling

Phase 1 requires automatic scheduling only.

The user does not manually trigger digests during normal operation.

### Scheduled Jobs

1. Source sync jobs
- periodic polling of all active sources.

2. Daily digest job
- default around midday;
- user-editable in settings.

3. Weekly digest job
- default on the night from Saturday to Sunday;
- user-editable in settings.

4. Evening observability report job
- daily evening email with Grafana screenshot and error summary.

### Catch-Up Logic

If the application was down during a scheduled digest window:
- on next startup, send the latest missed daily digest if one was missed;
- independently send the latest missed weekly digest if one was missed;
- do not backfill multiple historical daily or weekly digests.

## Email

### Digest Delivery

Digest email is sent:
- from a dedicated technical Gmail account;
- to a single user recipient address;
- through Gmail SMTP with an app password.

### Email Actions

Each email includes action links that:
- open the local site;
- persist feedback immediately;
- redirect the user to a relevant UI page.

### Email Config Management

The site supports:
- editing non-secret SMTP fields;
- replacing password through write-only input;
- test email sending.

### Observability Email

Each evening the system sends an operations email that includes:
- a Grafana screenshot for the previous 24 hours;
- a short textual summary of key metrics;
- an error and alert summary for the same period.

The application composes and sends this email itself rather than relying on Grafana Enterprise reporting.

## Observability

### Stack

Use a ready-made observability stack:
- Grafana OSS;
- Prometheus;
- Loki;
- OpenTelemetry Collector;
- grafana-image-renderer.

### Telemetry

The backend emits:
- application metrics;
- structured logs;
- job execution events;
- source adaptation and failure events;
- email delivery events;
- AI task performance and failure events.

### Alerts

Grafana alerting is used for operational alerting.

Alerts should cover:
- repeated source failures;
- digest send failure;
- observability report failure;
- Ollama unavailability;
- PostgreSQL unavailability;
- high parsing failure rate;
- excessive AI processing failures.

Technical issue emails may be batched to avoid spam.

## Security

Phase 1 security posture:
- no user accounts or roles;
- local mode may run without site login;
- future cloud mode should support a simple shared-secret style access gate;
- product secrets are write-only where appropriate;
- infrastructure secrets are external to the project folder.

## Deployment

### Local

Primary supported mode:
- Docker Compose;
- manual start after machine restart is acceptable;
- once running, jobs execute automatically.

### Future Cloud Readiness

The system should be structured so that later migration is straightforward:
- PostgreSQL already used from phase 1;
- secret access abstracted through `SecretStore`;
- observability stack already production-like;
- auth boundary reserved for future shared-secret gate.

## Explicit Non-Goals For Phase 1

- vector database or pgvector-based ranking;
- embedding search;
- video source ingestion;
- full article rendering;
- fine-tuning the local model;
- role-based access control;
- self-hosted custom observability UI replacing Grafana.

## Acceptance Criteria For Phase 1

The phase is successful when:
- a user can add text blog sources by plain URL through the site;
- the system can collect posts from both feed-based and fallback-parsed sources;
- the system generates Russian summaries locally;
- the system sends daily and weekly digests automatically;
- the system sends direct feedback links in digest emails;
- the system learns from feedback and uses it in ranking;
- the site exposes feed, want-to-read, sources, settings, digest history, and preference profile pages;
- SMTP settings can be configured through the site with write-only password handling;
- infrastructure secrets are read through Windows Credential Manager, not from the project folder;
- the observability stack is available through Grafana;
- the evening observability email includes Grafana screenshot and an error summary;
- source readaptation is supported when structures change.

## Notes

This specification intentionally describes the first implementation phase with change-friendly boundaries. Future phases are expected to adjust the product under agile change control directed through the project lead.
