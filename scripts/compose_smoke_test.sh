#!/usr/bin/env bash
# Simple Docker Compose smoke test for the Kafka demo
# Mirrors the CI job steps in .github/workflows/python.yml (compose-e2e)
#
# Usage:
#   scripts/compose_smoke_test.sh [--dry-run] [--no-build]
#
# Options:
#   --dry-run   Print what would be done without executing Docker commands
#   --no-build  Skip `docker compose build`
#
# Exit codes:
#   0 on success; non-zero on failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR%/scripts}"
cd "$REPO_ROOT"

# Defaults (can be overridden via env)
KAFKA_HEALTH_RETRIES="${KAFKA_HEALTH_RETRIES:-60}"      # ~120s (sleep 2)
VERIFY_RETRIES="${VERIFY_RETRIES:-120}"                 # 120s
SLEEP_SECS="${SLEEP_SECS:-2}"

DRY_RUN=0
SKIP_BUILD=0
ALWAYS_TEARDOWN=1
STACK_STARTED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-build)
      SKIP_BUILD=1
      shift
      ;;
    --no-teardown)
      ALWAYS_TEARDOWN=0
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

log() { printf "\n==== %s ====%s\n" "$1" ""; }

run_cmd() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] $*"
  else
    # shellcheck disable=SC2068
    $@
  fi
}

cleanup() {
  if [[ $ALWAYS_TEARDOWN -eq 1 && $STACK_STARTED -eq 1 ]]; then
    log "Tear down"
    run_cmd docker compose down -v --remove-orphans || true
  fi
}
trap cleanup EXIT

# Preflight checks
log "Preflight: check Docker & Compose"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY-RUN] docker --version"
  echo "[DRY-RUN] docker compose version"
else
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed or not in PATH" >&2
    exit 127
  fi
  docker --version >/dev/null
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 plugin is not available (need 'docker compose')" >&2
    exit 127
  fi
fi

# Step 1: Build images (optional)
if [[ $SKIP_BUILD -eq 0 ]]; then
  log "Build images"
  run_cmd docker compose build
else
  log "Skip build (per flag)"
fi

# Step 2: Start stack
log "Start stack"
run_cmd docker compose up -d
STACK_STARTED=1

# Step 3: Wait for Kafka to be healthy
log "Wait for Kafka health"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY-RUN] poll docker inspect -f '{{json .State.Health.Status}}' kafka for ${KAFKA_HEALTH_RETRIES}x every ${SLEEP_SECS}s"
else
  ok=0
  for i in $(seq 1 "$KAFKA_HEALTH_RETRIES"); do
    status=$(docker inspect -f '{{json .State.Health.Status}}' kafka 2>/dev/null || echo "null")
    echo "Kafka health: $status"
    if [[ "$status" == '"healthy"' ]]; then
      ok=1
      break
    fi
    sleep "$SLEEP_SECS"
  done
  if [[ $ok -ne 1 ]]; then
    echo "Kafka did not become healthy in time" >&2
    docker compose ps || true
    docker compose logs kafka || true
    exit 1
  fi
fi

# Step 4: Verify producer and consumer activity
log "Verify producer & consumer logs"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY-RUN] check kafka-producer logs for 'Sent: key=' and kafka-consumer logs for 'JSON (' or 'Plain' up to ${VERIFY_RETRIES}s"
else
  ok=0
  for i in $(seq 1 "$VERIFY_RETRIES"); do
    prod=$(docker logs kafka-producer 2>&1 | grep -c 'Sent: key=' || true)
    cons=$(docker logs kafka-consumer 2>&1 | grep -E -c 'JSON \(|Plain' || true)
    echo "Attempt $i: producer=$prod consumer=$cons"
    if [[ "$prod" -ge 3 && "$cons" -ge 3 ]]; then
      echo "Producer and consumer logs look good"
      ok=1
      break
    fi
    sleep 1
  done
  if [[ $ok -ne 1 ]]; then
    echo "Producer/consumer did not show expected activity" >&2
    docker compose logs || true
    exit 1
  fi
fi

log "Success!"
exit 0
