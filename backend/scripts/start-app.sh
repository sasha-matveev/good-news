#!/bin/sh
set -eu

exec uvicorn app.main:app --host 0.0.0.0 --port "${GOOD_NEWS_CONTENT_API_SERVICE_PORT:-8000}"
