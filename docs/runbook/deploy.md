# Production Deployment Runbook

Audience: ops engineer doing a first-time bootstrap or a routine
re-deploy of `indusia-visual-editor` on a single Linux host with public
DNS.

## 0. Prerequisites

| Requirement | Notes |
|---|---|
| Linux host (Ubuntu 22.04+ tested) | 4 vCPU, 8 GB RAM, 50 GB SSD minimum |
| Docker Engine 24+ + compose plugin | `docker compose version` must work |
| Public DNS A records | `indusia.<your-domain>` + `api.indusia.<your-domain>` both pointing at the host |
| Open ports 80 + 443 | Traefik handles ACME http-01 challenge on 80, terminates TLS on 443 |
| Ollama box (separate machine) | Reachable from the API host at `IVE_OLLAMA_URL`; we do NOT spin Ollama up in this compose |
| S3-compatible backup bucket | For pg_backup uploads; can defer with `IVE_BACKUP_LOCAL_ONLY=1` initially |

## 1. First-time bootstrap

```bash
# 1.1 — clone + cd
git clone https://github.com/alisadikinma/indusia-visual-editor.git
cd indusia-visual-editor

# 1.2 — author .env.prod (NOT committed). Use long random values.
cat > .env.prod <<'EOF'
IVE_AUTH_JWT_SECRET=<openssl rand -hex 32>
POSTGRES_PASSWORD=<openssl rand -hex 24>
IVE_OLLAMA_URL=https://ollama.internal:11434
ACME_EMAIL=ops@your-domain.example
PUBLIC_HOST=indusia.your-domain.example
PUBLIC_API_HOST=api.indusia.your-domain.example

# Backup target
AWS_S3_BUCKET=ive-backups
AWS_ACCESS_KEY_ID=<...>
AWS_SECRET_ACCESS_KEY=<...>
# AWS_ENDPOINT_URL=https://...   # only for non-AWS S3 (R2, MinIO, Wasabi)

# Optional observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
IVE_LOG_MODE=prod
EOF
chmod 600 .env.prod

# 1.3 — substitute your hostnames into infra/traefik/dynamic.yml
#       (the committed file uses `indusia.example` placeholders).
sed -i "s/indusia.example/${PUBLIC_HOST#*.}/g" infra/traefik/dynamic.yml

# 1.4 — patch traefik.yml ACME email
sed -i "s/ops@indusia.example/${ACME_EMAIL}/g" infra/traefik/traefik.yml

# 1.5 — build images + bring the stack up
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 1.6 — run Alembic migrations on first boot.
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api \
  alembic upgrade head
```

Wait ~60s for the ACME http-01 challenge to complete (Traefik logs:
`docker logs ive-traefik | grep -i acme`). Once you see "successfully
obtained certificate" for both hostnames, the stack is reachable.

Smoke:

```bash
curl -sS https://api.${PUBLIC_HOST#*.}/health | jq
# → {"status": true, "message": "ok", "data": {"version": "0.1.0"}}

curl -sS https://${PUBLIC_HOST} -o /dev/null -w "%{http_code}\n"
# → 200
```

## 2. Routine re-deploy

```bash
cd /opt/indusia-visual-editor
git fetch && git checkout main && git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod build api web
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d api web

# If the release adds a migration:
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api \
  alembic upgrade head
```

Traefik + postgres + backup-scheduler are untouched on a routine deploy.

## 3. Operator-visible signals

| Signal | Where | What it means |
|---|---|---|
| `X-Request-ID` response header | Every API response | Correlation key for `request_id` in JSON logs |
| `level: error` in logs | `docker logs ive-api` | Backend handled an exception; check trace context |
| `ofelia.job-exec.pg-backup` log | `docker logs ive-backup-scheduler` | Nightly backup result; failure = page |
| ACME renewal failure | `docker logs ive-traefik` | Certs renew automatically; failure = manual investigation |
| Frontend 502 | Traefik routing miss | Check `web` container is up and labeled |
| 401 storm on `/api/auth/refresh` | `request_id` traces | Possible refresh-token cookie eviction (browser side) |

## 4. Rolling back the API

```bash
git log --oneline -n 10           # find the last known-good commit
git checkout <sha>
docker compose -f docker-compose.prod.yml --env-file .env.prod build api
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d api
```

If the bad release shipped a schema migration, see
[disaster-recovery.md](disaster-recovery.md#downgrade-or-restore).

## 5. Environment variable reference

Authoritative list lives in [src/indusia_visual_editor/config.py](../../src/indusia_visual_editor/config.py).
Critical secrets:

| Var | Effect if wrong |
|---|---|
| `IVE_AUTH_JWT_SECRET` | Wrong secret = all bearer tokens invalid; users see 401 storm. Rotate by issuing a new secret + accepting one TTL window of forced re-login. |
| `IVE_AUTH_REFRESH_COOKIE_SECURE=true` | Required behind HTTPS; if `false` in prod, refresh cookies leak over HTTP redirects. |
| `POSTGRES_PASSWORD` | Mismatched between `api` container env and `postgres` container env = api can't connect. |
| `IVE_OLLAMA_URL` | Wrong URL = planner / pre-label / chat all 502 with `LlmConnectionError`. |
