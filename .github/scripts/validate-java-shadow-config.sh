#!/usr/bin/env bash
set -euo pipefail

required=(
  ALLOWED_EMAILS
  APP_MASTER_KEY_SECRET
  DATABASE_SECRET
  FIREBASE_PROJECT_ID
  GEMINI_API_KEY_SECRET
  OIDC_AUDIENCE
  PROJECT_ID
  PUBLIC_CONTENT_API_ORIGIN
  PUBLIC_FRONTEND_ORIGIN
  REGION
  RUNTIME_SERVICE_ACCOUNT
  SCHEDULER_INVOKER
)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "Missing required Java shadow configuration: $name" >&2
    exit 1
  fi
done

gcloud projects describe "$PROJECT_ID" --format='value(projectId)'
gcloud artifacts repositories describe good-news \
  --location "$REGION" \
  --project "$PROJECT_ID" \
  --format='value(name)'
for secret in "$DATABASE_SECRET" "$APP_MASTER_KEY_SECRET" "$GEMINI_API_KEY_SECRET"; do
  gcloud secrets describe "$secret" --project "$PROJECT_ID" --format='value(name)'
done
gcloud iam service-accounts describe "$RUNTIME_SERVICE_ACCOUNT" \
  --project "$PROJECT_ID" \
  --format='value(email)'
gcloud run deploy --help >/dev/null
