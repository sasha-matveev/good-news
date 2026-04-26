---
name: good-news-intake-and-routing
description: Use when a new request arrives and the project lead must route work to the correct MVP specialist instead of absorbing it directly.
---

# Good News Intake And Routing

## Overview

Every request enters through `project-lead`, but specialist work must stay specialist work. Route early. Keep the lead as coordinator only.

## Required Inputs

- `.codex/operating-model.md` for the canonical routing table, review matrix, and role boundaries;
- `.codex/routing-record.md` as the mandatory intake artifact for the active request.

## Required Workflow

1. Read `.codex/operating-model.md`.
2. Assign one primary owner using the canonical routing table.
3. Assign one mandatory reviewer or validator using the cross-agent review matrix.
4. Update `.codex/routing-record.md` before any specialist starts work.
5. Route the request only after the routing record names the current owner and reviewer or validator.

## Red Flags

- `project-lead` starts doing specialist analysis or drafting specs directly;
- work starts without `.codex/routing-record.md`;
- technical tradeoffs are made without `tech-lead`;
- runtime or observability changes happen without `platform-observability-engineer`;
- completion claims are made without QA coverage;
- written artifacts change without `technical-writer`;
- `project-lead` reports completion before the mandatory reviewer has finished.

## Output

Produce:
- updated `.codex/routing-record.md`;
- assigned owner role;
- assigned reviewer or validator role;
- supporting roles if needed;
- expected artifact, such as impact note, tech decision, platform change, QA report, or doc update.
