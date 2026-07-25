#!/usr/bin/env sh
set -eu

HARNESS_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_DIR=$(dirname "$HARNESS_DIR")

docker compose -f "$HARNESS_DIR/compose.yaml" up --build --wait

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker compose -f "$HARNESS_DIR/compose.yaml" logs --no-color java java-auth
  fi
  docker compose -f "$HARNESS_DIR/compose.yaml" down --volumes
  exit "$status"
}
trap cleanup EXIT

python3 -m pip install -e "$HARNESS_DIR"
mkdir -p "$REPOSITORY_DIR/artifacts"

export GOOD_NEWS_CONTRACT_PYTHON_URL=http://127.0.0.1:18000
export GOOD_NEWS_CONTRACT_JAVA_URL=http://127.0.0.1:18080
export GOOD_NEWS_CONTRACT_PYTHON_AUTH_URL=http://127.0.0.1:18001
export GOOD_NEWS_CONTRACT_JAVA_AUTH_URL=http://127.0.0.1:18081
export GOOD_NEWS_CONTRACT_PYTHON_DATABASE_URL=postgresql://good_news:good-news-contract@127.0.0.1:15432/good_news
export GOOD_NEWS_CONTRACT_JAVA_DATABASE_URL=postgresql://good_news:good-news-contract@127.0.0.1:25432/good_news
export GOOD_NEWS_CONTRACT_SIDE_EFFECTS_URL=http://127.0.0.1:18090
export GOOD_NEWS_CONTRACT_ROOT="$HARNESS_DIR"

python3 -m good_news_contract.cli --mode differential --report "$REPOSITORY_DIR/artifacts/backend-parity.md"
