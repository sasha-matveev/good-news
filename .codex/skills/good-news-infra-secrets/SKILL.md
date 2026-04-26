---
name: good-news-infra-secrets
description: Use when handling infrastructure or product secrets so they remain outside the repo and behind a replaceable abstraction.
---

# Good News Infra Secrets

## Overview

Infrastructure secrets must not live inside the repo or project folder. Local storage may be platform-specific, but business logic must not depend on that storage mechanism directly.

## Local Rule

Store outside the project folder:
- application master key
- database or service credentials

Read them through a dedicated abstraction instead of hard-coding the local storage mechanism into business logic.

## Product Secret Rule

Any user-configured secret is:
- accepted as write-only input;
- encrypted before persistence;
- never returned in plaintext.

## Cloud Readiness

The secret interface should be swappable later to:
- Docker secrets;
- Kubernetes secrets;
- managed secret stores.

## Avoid

- real secrets in repo files;
- direct business-logic dependency on a single OS-specific API;
- returning stored secrets to the UI.
