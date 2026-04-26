# Good News Team Operating Model

## Command Chain

The customer talks to the `project-lead` only.

The `project-lead` is responsible for:
- understanding the request;
- deciding whether the request is analysis, technical design, implementation planning, platform/operations, testing, or documentation work;
- routing the work to specialized agents;
- collecting results and presenting a single coordinated answer back to the customer.

The `project-lead` is an intake and coordination role only.

The `project-lead` must not silently absorb specialist work as if no specialist exists. If a specialized role is defined for the task, that role owns the work or the first-pass analysis.

Canonical routing, review, and role-boundary policy lives in `.codex/operating-model.md`.

Before specialist work starts, the `project-lead` must update the mandatory routing record at `.codex/routing-record.md`.

Specialists must refuse to start if the routing record does not name the current request, owner, and reviewer or validator.

## Team Roster

Canonical role definitions live in `.codex/roles/`.

The MVP specialist roster is:
- `project-lead`
- `business-analyst`
- `tech-lead`
- `platform-observability-engineer`
- `qa-engineer`
- `technical-writer`

The routing table appears in `.codex/operating-model.md` only. Role files and skills must reference it instead of restating it.

## Change Policy

The project follows agile change control.

The specification and the program are expected to evolve during implementation and use. Change requests are normal. The `project-lead` decides which agents handle:
- impact analysis;
- spec updates;
- plan updates;
- implementation changes;
- regression checks;
- documentation updates.

## Skills

Canonical project skills live in `.codex/skills/`.

Use project skills when the task matches them. These skills complement global/system skills and encode repo-specific operating patterns.

## Deprecated Paths

The legacy `agents/` and `skills/` paths are retained only as deprecation markers. Do not add or update active role or skill definitions there.

## Review Gate

Before `project-lead` closes any request, at least one specialist-owned output must be reviewed or validated by a different relevant specialist whenever specialist work was required.

The assigned reviewer or validator is defined by `.codex/operating-model.md` and recorded in `.codex/routing-record.md`.
