# Disaster Recovery Runbook

Three failure classes are covered here. In all three, the goal is RTO
&lt; 1 hour and RPO ≤ 24h (matches the daily backup schedule).

## 1. Postgres data loss / corruption

### Detect

- `ive-api` logs flooding with `sqlalchemy.exc.OperationalError` or
  `asyncpg.exceptions.PostgresError`
- `pg_isready` fails inside the `ive-postgres` container
- Manual: `docker compose exec postgres psql -U ive -c "\dt"` returns
  fewer tables than expected

### Restore

Backups are written nightly to `s3://$AWS_S3_BUCKET/$AWS_S3_PREFIX/`
(default prefix `pg-backups/`), filename `ive-<UTC-timestamp>.dump.gz`.
Pick the most recent dump older than the corruption window.

```bash
# 1. Stop the API so no writes interleave with the restore.
docker compose -f docker-compose.prod.yml --env-file .env.prod stop api

# 2. Identify the dump to restore (newest before incident).
docker compose -f docker-compose.prod.yml --env-file .env.prod exec postgres \
  aws s3 ls "s3://$AWS_S3_BUCKET/pg-backups/" | tail -20

# 3. Restore. The pg_restore.sh script accepts an s3:// URL directly —
#    it downloads to a tempdir, gunzip's, then `pg_restore --clean
#    --if-exists --create` against the live cluster. The --clean flag
#    drops + recreates the target schema, so this is idempotent.
docker compose -f docker-compose.prod.yml --env-file .env.prod exec postgres \
  bash /usr/local/bin/ive-scripts/pg_restore.sh \
    s3://$AWS_S3_BUCKET/pg-backups/ive-20260524-020001.dump.gz

# 4. Bring the API back up + smoke /health.
docker compose -f docker-compose.prod.yml --env-file .env.prod start api
curl -sS https://api.${PUBLIC_HOST#*.}/health
```

### Verify

- `SELECT count(*) FROM projects;` and compare against last known
  business count
- Login + open a recent project → check assets render

## 2. Bad migration (downgrade or restore)

A migration that ships in a release ran but corrupted data, or the
release rollback (§4 of [deploy.md](deploy.md)) requires reverting
schema.

### Option A — Alembic downgrade (preferred when reversible)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api \
  alembic downgrade -1
```

Only viable when the migration's `downgrade()` is real (not a `pass`).
Check the migration file before running.

### Option B — Restore from backup

If `downgrade()` is a stub or the data is already corrupted by the bad
migration, fall back to §1 (Postgres restore) using a dump from BEFORE
the migration ran. Restoring overwrites schema AND data — accept the
lost transactions or replay them from log analysis.

## 3. Selected-model rollback (edge regression)

A bad model was promoted via Gate 2 and an edge node now refuses good
boards. The edge's `.cache/selected_model.json` points at the bad
version, but we don't redeploy edges — we send a refresh webhook.

### Detect

- Edge box's inspection rejection rate climbs immediately after a
  deployment row was inserted (`SELECT * FROM deployments ORDER BY
  deployed_at DESC LIMIT 1`)
- Operator at the factory reports false-fail spike

### Roll back via PUT /api/edges/{id}/pin

The edge registry supports per-edge version pinning. The visual editor
pushes the pinned version on the next webhook fire, and the edge picks
it up via its normal pull cycle.

```bash
# 1. Find the edge that needs rollback
curl -sS https://api.${PUBLIC_HOST#*.}/api/edges \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.data[]'

# 2. Pin to the prior known-good model version
curl -sS -X PUT \
  https://api.${PUBLIC_HOST#*.}/api/edges/<edge-id>/pin \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_name": "<pcb_slug>", "version": "<known-good-tag>"}'

# 3. Trigger a deployment notification re-fire (any new Gate 2 push will
#    notify the edge, OR the admin can re-promote the prior train_run).
```

After confirming the rollback worked, debug the bad model in a clean
session before un-pinning the edge.

## 4. Full host loss

Restoring from scratch:

1. Provision a new host matching §0 of [deploy.md](deploy.md)
2. Run §1 bootstrap (clone, .env.prod, `docker compose up -d`)
3. Restore postgres from latest S3 dump (§1 above), then run
   `alembic upgrade head` if newer than the dump
4. Update DNS A records to point at the new host IP (if changed)
5. Re-issue ACME certs (Traefik does this automatically on first request
   to each hostname)

The S3 backup is the only persistent state — everything else (Docker
images, code, traefik certs) can be reconstructed.

## 5. Drill schedule

Quarterly DR drill, signed off by the operator:

1. Stand up a sandbox host (or use a staging environment)
2. Restore the previous night's prod dump into the sandbox
3. Smoke `/health` + create a test project + verify a known prediction
4. Document the actual restore time in this file's appendix

Last drill: TBD (record `YYYY-MM-DD`, RTO observed)
