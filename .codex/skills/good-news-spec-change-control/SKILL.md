---
name: good-news-spec-change-control
description: Use when requirements, constraints, or scope change and the team must propagate the change through analysis, technical direction, docs, and validation.
---

# Good News Spec Change Control

## Overview

This project is agile by design. Change is normal. The requirement is disciplined propagation, not resistance.

## Workflow

1. `project-lead` confirms `.codex/routing-record.md` is updated for the active request.
2. `business-analyst` clarifies the change and scope boundary.
3. `tech-lead` evaluates technical and architectural impact.
4. `technical-writer` updates the relevant spec, plan, or operator doc.
5. The owning specialist executes the change.
6. `qa-engineer` verifies the updated behavior.
7. The mandatory reviewer named in `.codex/operating-model.md` reviews the owned artifact if that review is not already covered by step 6.
8. `project-lead` communicates the coordinated result.

## Must Capture

- what changed;
- why it changed;
- what existing artifact became stale;
- who owns each follow-up;
- what still needs verification.

## Anti-Pattern

Do not treat a verbal decision as if the system already changed. Update the artifact and route the follow-up work.
