---
name: good-news-digest-ranking
description: Use when implementing or changing ranking, digest inclusion order, or preference learning for the Good News MVP.
---

# Good News Digest Ranking

## Overview

MVP ranking is hybrid and inspectable. Explicit feedback dominates. AI can summarize and explain, but ranking logic must remain understandable outside the model.

## Phase 1 Signals

- explicit feedback: `interesting`, `not_interesting`, `want_to_read`
- source affinity
- topic affinity
- format of material
- practical engineering orientation
- estimated technical depth

## Required Behavior

- consider all collected publications in the digest window;
- sort by estimated interest;
- show the top 5 in the email;
- mention how many lower-ranked posts remain;
- expose the full list on the site.

## Avoid

- hiding ranking logic inside the LLM;
- adding vector search without an explicit scope change;
- optimizing for sophistication over controllable behavior.
