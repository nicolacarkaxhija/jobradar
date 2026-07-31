#!/usr/bin/env bash
# Push every non-empty value from a local .env into the private data repo's
# GitHub Actions secrets. Idempotent — re-run after rotating a credential.
#
#   ./scripts/sync-secrets.sh [.env] [owner/data-repo]
#
# Requires: gh (authenticated). Values are passed on stdin, never as argv,
# so they don't leak into the process list or shell history.
set -euo pipefail

ENV_FILE="${1:-.env}"
REPO="${2:-nicolacarkaxhija/jobradar-data}"

[ -f "$ENV_FILE" ] || { echo "no such file: $ENV_FILE" >&2; exit 1; }

set_count=0
skipped=()

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  key="${line%%=*}"
  value="${line#*=}"
  key="$(printf '%s' "$key" | tr -d '[:space:]')"
  # strip surrounding quotes if present
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  if [ -z "$value" ]; then
    skipped+=("$key")
    continue
  fi
  printf '%s' "$value" | gh secret set "$key" --repo "$REPO" --body -
  echo "set $key"
  set_count=$((set_count + 1))
done < "$ENV_FILE"

echo
echo "$set_count secret(s) synced to $REPO"
if [ ${#skipped[@]} -gt 0 ]; then
  echo "empty, left unset: ${skipped[*]}"
fi
