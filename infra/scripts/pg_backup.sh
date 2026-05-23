#!/usr/bin/env bash
# Indusia Visual Editor — Postgres backup.
#
# Designed to run INSIDE the postgres container via `docker exec`, which
# means pg_dump is already on PATH and PGHOST is implicitly localhost.
# The ofelia scheduler in docker-compose.prod.yml fires this nightly.
#
# Env (all optional unless flagged required):
#   PGUSER        — required; defaults to `ive`
#   PGDATABASE    — required; defaults to `ive`
#   PGPASSWORD    — required when authenticating as a non-trust user
#   BACKUP_DIR    — host directory mounted into the container (default
#                   /var/backups/ive). MUST be persistent.
#   RETENTION_DAYS — default 14
#   IVE_BACKUP_LOCAL_ONLY — if set, S3 upload is skipped (CI + dev path)
#   AWS_S3_BUCKET — required when IVE_BACKUP_LOCAL_ONLY is unset
#   AWS_S3_PREFIX — default `pg-backups`
#   AWS_ENDPOINT_URL — optional, for S3-compatible providers (R2 / MinIO)
#
# Output: pg_dump -Fc (custom format) + gzip, timestamped filename
#         <BACKUP_DIR>/ive-<YYYYmmdd-HHMMSS>.dump.gz
# Exit non-zero on any failure; ofelia surfaces the log line.

set -euo pipefail

: "${PGUSER:=ive}"
: "${PGDATABASE:=ive}"
: "${BACKUP_DIR:=/var/backups/ive}"
: "${RETENTION_DAYS:=14}"
: "${AWS_S3_PREFIX:=pg-backups}"

mkdir -p "$BACKUP_DIR"
TS="$(date -u +%Y%m%d-%H%M%S)"
DUMP_PATH="$BACKUP_DIR/ive-$TS.dump.gz"

echo "[pg_backup] dumping $PGDATABASE -> $DUMP_PATH"
pg_dump --format=custom --no-owner --no-privileges \
        --username="$PGUSER" --dbname="$PGDATABASE" \
  | gzip --best > "$DUMP_PATH"

ls -lh "$DUMP_PATH"

# Optional S3 upload. Set IVE_BACKUP_LOCAL_ONLY=1 (CI + smoke tests) to skip.
if [ -z "${IVE_BACKUP_LOCAL_ONLY:-}" ]; then
  : "${AWS_S3_BUCKET:?S3 bucket required when IVE_BACKUP_LOCAL_ONLY is unset}"
  AWS_CMD=(aws s3 cp "$DUMP_PATH" "s3://$AWS_S3_BUCKET/$AWS_S3_PREFIX/$(basename "$DUMP_PATH")")
  if [ -n "${AWS_ENDPOINT_URL:-}" ]; then
    AWS_CMD=(aws --endpoint-url "$AWS_ENDPOINT_URL" s3 cp "$DUMP_PATH" "s3://$AWS_S3_BUCKET/$AWS_S3_PREFIX/$(basename "$DUMP_PATH")")
  fi
  echo "[pg_backup] uploading to s3://$AWS_S3_BUCKET/$AWS_S3_PREFIX/"
  "${AWS_CMD[@]}"
else
  echo "[pg_backup] IVE_BACKUP_LOCAL_ONLY=1, skipping S3 upload"
fi

# Retention: prune local dumps older than RETENTION_DAYS. S3 lifecycle rules
# handle remote retention — keep them in the bucket policy, not here.
echo "[pg_backup] pruning local dumps older than ${RETENTION_DAYS}d"
find "$BACKUP_DIR" -name 'ive-*.dump.gz' -mtime "+$RETENTION_DAYS" -delete || true

echo "[pg_backup] done"
