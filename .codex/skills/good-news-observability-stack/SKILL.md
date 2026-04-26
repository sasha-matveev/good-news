---
name: good-news-observability-stack
description: Use when implementing or changing monitoring, telemetry, alerts, or operator visibility for the Good News MVP.
---

# Good News Observability Stack

## Overview

Use established observability products as the primary operations surface. Do not build a custom monitoring UI for operator workflows.

## Default Stack

- Grafana OSS
- Prometheus
- Loki
- OpenTelemetry Collector
- grafana-image-renderer

## Rules

- product UI is for end-user workflows, not primary operations monitoring;
- operational visibility lives in Grafana;
- backend emits metrics and structured logs;
- alerts cover source failures, digest failures, AI failures, and runtime outages;
- any emailed operational report should draw from Grafana-backed telemetry.

## Avoid

- inventing a homegrown observability console;
- mixing operator telemetry with customer-facing page concerns;
- depending on enterprise-only features as the only path.
