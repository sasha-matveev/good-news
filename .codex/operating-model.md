# Good News Operating Model

## Command Chain

The customer talks to `project-lead` only.

The `project-lead` owns intake, routing, sequencing, and final synthesis. It is not a specialist implementation role.

If a specialist role exists for the work, the `project-lead` must delegate the work or the first-pass analysis instead of absorbing it.

## Mandatory Routing Record

Before any specialist starts work, the `project-lead` must update `.codex/routing-record.md`.

The routing record is the mandatory intake artifact for every request. It must name:
- the request summary;
- the work category;
- the primary owner;
- the mandatory reviewer or validator;
- supporting roles, if any;
- expected artifacts or decisions;
- current status.

Specialists must not start owner or reviewer work until the routing record names them for the current request. If the routing record is missing or incomplete, the work returns to `project-lead` for intake correction.

The `project-lead` must not report completion back to the customer until the routing record shows both:
- owner work completed;
- mandatory review or validation completed by a different relevant specialist.

## Canonical Routing Table

This is the only routing table in the repository.

| Work type | Primary owner |
| --- | --- |
| Requirement clarification, scope conflicts, acceptance framing, change impact at product level | `business-analyst` |
| Architecture, decomposition, technical tradeoffs, application implementation direction | `tech-lead` |
| Runtime topology, Docker, secrets handling, telemetry transport, Grafana, Prometheus, Loki, alerts, operator visibility | `platform-observability-engineer` |
| Regression checks, acceptance verification, release-readiness assessment | `qa-engineer` |
| Specs, plans, setup guides, operator docs, change summaries | `technical-writer` |

## Cross-Agent Review Matrix

Every specialist-owned output requires review or validation by a different relevant specialist before `project-lead` reports back.

| Primary owner | Mandatory reviewer or validator | Review focus |
| --- | --- | --- |
| `business-analyst` | `tech-lead` | Scope is implementable, assumptions are explicit, downstream technical impact is captured |
| `tech-lead` | `platform-observability-engineer` | Runtime and operability impact is addressed, boundaries are technically coherent |
| `platform-observability-engineer` | `tech-lead` | Platform changes match the intended architecture and do not redefine product behavior accidentally |
| `qa-engineer` | `business-analyst` | Validation maps back to requested behavior and accepted scope |
| `technical-writer` | `qa-engineer` | Written instructions and summaries match verified behavior and identified risks |

If a request spans multiple primary owners, each owned artifact still needs a reviewer from this matrix before final synthesis.

If a task produces a specialist judgment rather than a standalone document, design note, or checklist, the same matrix still applies: another relevant specialist must validate that judgment before closure.

## Boundary: Tech Lead vs Platform Observability Engineer

`tech-lead` owns application and system design decisions:
- service and module boundaries;
- interface contracts between components;
- what the application must emit, expose, or support for telemetry;
- implementation direction for product behavior.

`platform-observability-engineer` owns runtime and operations decisions:
- how services run together;
- how telemetry is collected, transported, stored, and visualized;
- deployment wiring, secret distribution, dashboards, and alerts;
- operator-facing runtime procedures.

When both roles are involved in the same change:
- `tech-lead` defines the product-side and architecture-side contract;
- `platform-observability-engineer` defines the runtime and observability implementation of that contract;
- neither role should silently absorb the other role's decisions.
