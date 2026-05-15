#!/bin/sh
set -eu

exec uvicorn app.analysis_llm_service.main:app --host 0.0.0.0 --port "${GOOD_NEWS_ANALYSIS_SERVICE_PORT:-8100}"
