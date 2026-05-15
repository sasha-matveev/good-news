#!/bin/sh
set -eu

exec uvicorn app.delivery_service.main:app --host 0.0.0.0 --port "${GOOD_NEWS_DELIVERY_SERVICE_PORT:-8300}"
