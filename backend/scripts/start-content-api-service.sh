#!/bin/sh
set -eu

exec uvicorn app.content_api_service.main:app --host 0.0.0.0 --port "${GOOD_NEWS_CONTENT_API_SERVICE_PORT:-8000}"
