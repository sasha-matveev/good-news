---
name: good-news-release-readiness
description: Use when a milestone is about to be presented as complete and the team needs focused validation of MVP behavior and operational readiness.
---

# Good News Release Readiness

## Overview

Completion claims require coverage of core flows, not isolated subsystem success.

## Minimum Checks

- source onboarding or update flow works for representative inputs;
- digest generation still includes and orders posts correctly;
- feedback persistence still works;
- secret-handling paths remain within the approved boundaries;
- scheduler or automation paths are verified when touched;
- observability still receives telemetry when platform behavior changes.

## Output

Return:
- findings first;
- verified coverage;
- unverified areas;
- residual risks;
- explicit release recommendation.
