#!/usr/bin/env bash
# Restore dev state on Macbook from a .sync/ bundle produced by sync-to-macbook.ps1.
#
# Prereq di Mac:
#   - Docker Desktop running (arm64 native)
#   - Homebrew + git + poetry + pnpm (lihat README)
#   - Repo sudah di-clone & cd ke root
#   - .sync/ folder dari PC sudah di-drop di root
#
# Usage:
#   ./scripts/sync-from-pc.sh
#   ./scripts/sync-from-pc.sh --skip-storage

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_STORAGE=0
for arg in "$@"; do
  case "$arg" in
    --skip-storage) SKIP_STORAGE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SYNC_DIR="$REPO_ROOT/.sync"
[[ -d "$SYNC_DIR" ]] || { echo "missing .sync/ — copy it from PC first" >&2; exit 1; }
[[ -f "$SYNC_DIR/ive-db.dump" ]] || { echo "missing .sync/ive-db.dump" >&2; exit 1; }

if [[ -f "$SYNC_DIR/MANIFEST.txt" ]]; then
  echo "==> snapshot manifest:"
  cat "$SYNC_DIR/MANIFEST.txt"
  echo
fi

echo "==> git pull origin main"
git fetch origin
git checkout main
git pull --ff-only origin main

# .env bootstrap
if [[ ! -f .env ]]; then
  echo "==> .env not found, copying from .env.example"
  cp .env.example .env
  echo "    edit .env to set IVE_AUTH_JWT_SECRET + Ollama URL before booting api"
fi

echo "==> docker compose up postgres (arm64 native rebuild)"
docker compose -f docker-compose.dev.yml up -d postgres

# wait for healthy
echo "==> waiting for ive-postgres-dev healthcheck"
for i in $(seq 1 30); do
  status=$(docker inspect ive-postgres-dev --format '{{.State.Health.Status}}' 2>/dev/null || echo "starting")
  if [[ "$status" == "healthy" ]]; then break; fi
  sleep 2
done
[[ "$status" == "healthy" ]] || { echo "postgres did not become healthy" >&2; exit 1; }

echo "==> restoring database from .sync/ive-db.dump"
# Copy dump into the container so pg_restore can read it directly (avoids
# stdin-piping quirks with custom-format archives).
docker cp "$SYNC_DIR/ive-db.dump" ive-postgres-dev:/tmp/ive-db.dump
docker exec ive-postgres-dev pg_restore \
  -U ive -d ive \
  --clean --if-exists --no-owner --no-privileges \
  /tmp/ive-db.dump
docker exec ive-postgres-dev rm -f /tmp/ive-db.dump

# Verify row counts match the PC snapshot
if [[ -f "$SYNC_DIR/row-counts.txt" ]]; then
  echo "==> verifying row counts vs PC snapshot"
  mismatch=0
  while IFS=$'\t' read -r tbl expected; do
    [[ -z "$tbl" ]] && continue
    actual=$(docker exec ive-postgres-dev psql -U ive -d ive -tAc "SELECT COUNT(*) FROM $tbl" 2>/dev/null | tr -d '[:space:]')
    if [[ "$actual" == "$expected" ]]; then
      printf "    OK   %-20s %s rows\n" "$tbl" "$actual"
    else
      printf "    DIFF %-20s expected=%s actual=%s\n" "$tbl" "$expected" "$actual"
      mismatch=1
    fi
  done < "$SYNC_DIR/row-counts.txt"
  [[ $mismatch -eq 0 ]] || { echo "row count mismatch — investigate before using" >&2; exit 1; }
fi

if [[ $SKIP_STORAGE -eq 0 && -f "$SYNC_DIR/storage.tar.gz" ]]; then
  echo "==> restoring storage/ uploads"
  tar -xzf "$SYNC_DIR/storage.tar.gz" -C "$REPO_ROOT"
fi

echo
echo "Done. Next steps di Mac:"
echo "  poetry install            # backend deps (first time only)"
echo "  poetry run alembic upgrade head"
echo "  poetry run uvicorn indusia_visual_editor.main:app --port 8002 --reload"
echo
echo "  cd web && pnpm install    # frontend deps (first time only)"
echo "  pnpm dev                  # http://localhost:5173"
