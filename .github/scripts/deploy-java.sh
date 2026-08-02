#!/usr/bin/env bash
set -euo pipefail

required=(
  ALLOWED_EMAILS
  CANDIDATE_SHA
  IMAGE
  PROJECT_ID
  PUBLIC_CONTENT_API_ORIGIN
  PUBLIC_FRONTEND_ORIGIN
  REGION
  SERVICE
)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "Missing required Java deployment value: $name" >&2
    exit 1
  fi
done

database_secret=${DATABASE_SECRET:-good-news-db-url}
master_key_secret=${APP_MASTER_KEY_SECRET:-good-news-app-master-key}
gemini_secret=${GEMINI_API_KEY_SECRET:-good-news-gemini-api-key}
deploy_environment=${DEPLOY_ENVIRONMENT:-prod}
firebase_project_id=${FIREBASE_PROJECT_ID:-$PROJECT_ID}
runtime_service_account=${RUNTIME_SERVICE_ACCOUNT:-good-news-app@${PROJECT_ID}.iam.gserviceaccount.com}
scheduler_invoker=${SCHEDULER_INVOKER:-scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com}
oidc_audience=${OIDC_AUDIENCE:-$PUBLIC_CONTENT_API_ORIGIN}
revision_tag="release-${CANDIDATE_SHA:0:12}"

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --tag "$revision_tag" \
  --no-traffic \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$runtime_service_account" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --concurrency 20 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 1 \
  --port 8080 \
  --startup-probe="httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=0,timeoutSeconds=3,periodSeconds=5,failureThreshold=12" \
  --set-secrets="GOOD_NEWS_DATABASE_URL=${database_secret}:latest,GOOD_NEWS_APP_MASTER_KEY=${master_key_secret}:latest,GOOD_NEWS_GEMINI_API_KEY=${gemini_secret}:latest" \
  --set-env-vars="^@@^GOOD_NEWS_ENV=${deploy_environment}@@GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE=0@@GOOD_NEWS_DATABASE_POOL_MAX_SIZE=4@@GOOD_NEWS_DATABASE_POOL_ACQUIRE_TIMEOUT=2s@@GOOD_NEWS_DATABASE_CONNECT_TIMEOUT=5s@@GOOD_NEWS_DATABASE_OPERATION_TIMEOUT=30s@@GOOD_NEWS_DATABASE_POOL_IDLE_TIMEOUT=10m@@GOOD_NEWS_DATABASE_POOL_MAX_LIFE_TIME=30m@@GOOD_NEWS_FIREBASE_PROJECT_ID=${firebase_project_id}@@GOOD_NEWS_ALLOWED_EMAILS=${ALLOWED_EMAILS}@@GOOD_NEWS_SCHEDULER_INVOKER=${scheduler_invoker}@@GOOD_NEWS_OIDC_AUDIENCE=${oidc_audience}@@GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN=${PUBLIC_CONTENT_API_ORIGIN}@@GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=${PUBLIC_FRONTEND_ORIGIN}"

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
