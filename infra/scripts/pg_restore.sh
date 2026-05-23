#!/usr/bin/env bash
# Indusia Visual Editor — Postgres restore.
#
# Two modes:
#   1. Local file:   pg_restore.sh /var/backups/ive/ive-<ts>.dump.gz
#   2. From S3:      pg_restore.sh s3://bucket/path/ive-<ts>.dump.gz
#
# Env (all optional unless flagged required):
#   PGUSER       — required; defaults to `ive`
#   PGDATABASE   — required; defaults to `ive`
#   PGPASSWORD   — required when authenticating as a non-trust user
#   AWS_ENDPOINT_URL — optional S3-compatible endpoint
#
# Behaviour: drops + recreates the target schema (--clean --if-exists --create)
# so the restore is idempotent. Aborts on any error.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: pg_restore.sh <dump-path-or-s3-url>" >&2
  exit 2
fi

SOURCE="$1"
: "${PGUSER:=ive}"
: "${PGDATABASE:=ive}"

WORKDIR="$(mktemp -d -t ive-restore-XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

LOCAL_PATH="$SOURCE"
case "$SOURCE" in
  s3://*)
    LOCAL_PATH="$WORKDIR/$(basename "$SOURCE")"
    AWS_CMD=(aws s3 cp "$SOURCE" "$LOCAL_PATH")
    if [ -n "${AWS_ENDPOINT_URL:-}" ]; then
      AWS_CMD=(aws --endpoint-url "$AWS_ENDPOINT_URL" s3 cp "$SOURCE" "$LOCAL_PATH")
    fi
    echo "[pg_restore] downloading $SOURCE"
    "${AWS_CMD[@]}"
    ;;
esac

if [ ! -f "$LOCAL_PATH" ]; then
  echo "[pg_restore] backup file not found: $LOCAL_PATH" >&2
  exit 3
fi

UNCOMPRESSED="$WORKDIR/dump.pgcustom"
echo "[pg_restore] decompressing -> $UNCOMPRESSED"
gunzip -c "$LOCAL_PATH" > "$UNCOMPRESSED"

echo "[pg_restore] restoring into $PGDATABASE (clean + create)"
pg_restore --clean --if-exists --no-owner --no-privileges \
           --username="$PGUSER" --dbname="$PGDATABASE" \
           "$UNCOMPRESSED"

echo "[pg_restore] done"
