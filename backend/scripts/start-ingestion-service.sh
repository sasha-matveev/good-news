#!/bin/sh
set -eu

exec uvicorn app.source_ingestion_service.main:app --host 0.0.0.0 --port "${GOOD_NEWS_SOURCE_INGESTION_SERVICE_PORT:-8200}"
