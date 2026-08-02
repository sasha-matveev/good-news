#!/usr/bin/env bash
set -euo pipefail

required=(
  ALLOWED_EMAILS
  APP_MASTER_KEY_SECRET
  CANDIDATE_SHA
  DATABASE_SECRET
  FIREBASE_PROJECT_ID
  GEMINI_API_KEY_SECRET
  IMAGE
  OIDC_AUDIENCE
  PROJECT_ID
  PUBLIC_CONTENT_API_ORIGIN
  PUBLIC_FRONTEND_ORIGIN
  REGION
  RUNTIME_SERVICE_ACCOUNT
  SCHEDULER_INVOKER
  SERVICE
  SHADOW_ENVIRONMENT
)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "Missing required deployment value: $name" >&2
    exit 1
  fi
done

case "$SHADOW_ENVIRONMENT" in
  staging)
    traffic=()
    ;;
  prod)
    traffic=(--no-traffic)
    ;;
  *)
    echo "SHADOW_ENVIRONMENT must be staging or prod" >&2
    exit 1
    ;;
esac

revision_tag="shadow-${CANDIDATE_SHA:0:12}"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --tag "$revision_tag" \
  "${traffic[@]}" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --concurrency 20 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 1 \
  --port 8080 \
  --startup-probe="httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=0,timeoutSeconds=3,periodSeconds=5,failureThreshold=12" \
  --set-secrets="GOOD_NEWS_DATABASE_URL=${DATABASE_SECRET}:latest,GOOD_NEWS_APP_MASTER_KEY=${APP_MASTER_KEY_SECRET}:latest,GOOD_NEWS_GEMINI_API_KEY=${GEMINI_API_KEY_SECRET}:latest" \
  --set-env-vars="^@@^GOOD_NEWS_ENV=${SHADOW_ENVIRONMENT}@@GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE=0@@GOOD_NEWS_DATABASE_POOL_MAX_SIZE=4@@GOOD_NEWS_DATABASE_POOL_ACQUIRE_TIMEOUT=2s@@GOOD_NEWS_DATABASE_CONNECT_TIMEOUT=5s@@GOOD_NEWS_DATABASE_OPERATION_TIMEOUT=30s@@GOOD_NEWS_DATABASE_POOL_IDLE_TIMEOUT=10m@@GOOD_NEWS_DATABASE_POOL_MAX_LIFE_TIME=30m@@GOOD_NEWS_FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID}@@GOOD_NEWS_ALLOWED_EMAILS=${ALLOWED_EMAILS}@@GOOD_NEWS_SCHEDULER_INVOKER=${SCHEDULER_INVOKER}@@GOOD_NEWS_OIDC_AUDIENCE=${OIDC_AUDIENCE}@@GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN=${PUBLIC_CONTENT_API_ORIGIN}@@GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=${PUBLIC_FRONTEND_ORIGIN}"

gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format=json > service.json
revision=$(jq -r '.status.latestReadyRevisionName' service.json)
revision_url=$(jq -r \
  --arg tag "$revision_tag" \
  --arg revision "$revision" \
  '.status.traffic[] | select(.tag == $tag and .revisionName == $revision) | .url' \
  service.json)
test -n "$revision"
test -n "$revision_url"

echo "revision=$revision" >> "$GITHUB_OUTPUT"
echo "revision_url=$revision_url" >> "$GITHUB_OUTPUT"
