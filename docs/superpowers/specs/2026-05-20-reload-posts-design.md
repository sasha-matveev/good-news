# Reload Posts Design

## Goal

Replace the overly specific `Refresh post dates` action with a true `Reload posts` flow for an existing source.

## Approved Behavior

- The UI action is renamed from `Refresh post dates` to `Reload posts`.
- Before running, the UI shows a warning that recent posts for that source will be deleted and reloaded.
- "Recent" means the last 2 months using:
  - `published_at` when present
  - otherwise `created_at`
- The reload is a hard reload for only that recent window:
  - delete matching posts for the source
  - delete dependent rows tied to those posts
  - fetch and persist posts for that source again
- The existing per-source `Sync` action remains a lightweight fetch for new posts and is not repurposed.

## Backend Design

- Add a dedicated reload operation for a single source.
- The reload operation must not depend on `last_success_at`, because the existing sync path intentionally skips already-seen historical feed entries.
- The reload operation deletes recent posts first, then directly parses and persists source posts again instead of routing through the existing incremental sync filter.
- The reload API returns counts that let the UI explain what happened.

## UI Design

- Rename the action and tooltip text to `Reload posts`.
- Add a confirmation warning before the destructive action runs.
- Update the per-source log wording to reflect deletion and reloading, not date refresh.

## Testing

- Backend unit tests for the reload service behavior and recent-window selection.
- Backend API tests for the new endpoint.
- Frontend tests for the renamed action, warning, and API call.
