---
name: good-news-source-onboarding
description: Use when adding or repairing a content source, especially when deterministic discovery may need a stored fallback strategy.
---

# Good News Source Onboarding

## Overview

Prefer deterministic source discovery first and AI-assisted parsing second. The onboarding path must stay explainable and repeatable.

## Order Of Operations

1. Normalize the submitted source URL.
2. Try standard RSS and Atom discovery.
3. Inspect HTML for feed links and common source patterns.
4. If no durable feed exists, detect listing pages and article links from HTML.
5. Use AI only to assist structure recognition or candidate extraction.
6. Persist the working strategy so future polling is repeatable.

## Re-Adaptation

When a source starts failing:
- mark it as needing re-adaptation;
- emit an operational event;
- rerun the onboarding flow;
- replace the stored strategy only after a new one succeeds.

## Avoid

- making the LLM the primary scraper;
- using one-off parsing logic with no stored strategy;
- silently dropping failing sources.
