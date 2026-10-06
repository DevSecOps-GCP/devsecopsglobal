# DevSecOps Global: LearnHub

A small learning platform: learners sign up, log in and watch demo videos; the admin uploads and
publishes them. It's the application deployed on the GKE platform described in the
`infrastructure` repo.

| Layer    | Tech                                            | In GCP                                  |
|----------|-------------------------------------------------|-----------------------------------------|
| Frontend | React 19 + Vite, served by nginx-unprivileged   | GKE (`prod` cluster)                    |
| Backend  | FastAPI, SQLAlchemy (async), Alembic            | GKE (`prod` cluster)                    |
| Database | PostgreSQL                                      | Cloud SQL, private IP only              |
| Cache    | Redis                                           | Memorystore, AUTH + TLS                 |
| Videos   | Object storage via signed URLs                  | GCS bucket, private                     |
| Secrets  | env vars                                        | HashiCorp Vault → Vault Secrets Operator |

## How it works

```
browser ──/api/*──► backend ──► Postgres  (users, video metadata)
   │                   └──────► Redis     (catalog cache, view counters, login rate limits)
   │
   └──signed URL──► GCS                   (video bytes: direct upload and streaming)
```

- **Routing**: one hostname. The load balancer sends `/api/*` to the backend and everything else
  to the frontend, so there is no CORS and the session cookie stays first-party.
- **Auth**: argon2 password hashes; the session is a JWT in an `HttpOnly`, `Secure`,
  `SameSite=Strict` cookie (no token in JS, no CSRF). Logins are rate limited per account and per
  IP in Redis.
- **Videos never pass through the API.** Upload is `create → PUT to signed URL → complete →
  publish`; playback gets a signed GET URL that expires after 2 hours. This avoids the load
  balancer's request timeout on large files and keeps the bucket private. On GKE the pod signs
  through the IAM `signBlob` API (Workload Identity has no key file).
- **Redis is a cache, not a dependency**: every Redis call fails open. If Memorystore is down the
  app serves from Postgres, `/readyz` reports `redis: degraded`, and pods stay ready.
- **Observability**: JSON logs (Cloud Logging `severity` field), Prometheus metrics on `/metrics`
  (latency per route, cache hit/miss, logins, signups, views). `/healthz`, `/readyz` and
  `/metrics` sit outside `/api`, so the public load balancer never exposes them.

## Run locally

```bash
cp .env.example .env          # choose your admin email/password
docker compose up --build     # http://localhost:8080
```

`migrate` runs `alembic upgrade head` and creates the admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`;
in the cluster the same command runs as an ArgoCD PreSync Job. Log in with that account, open
**Admin**, upload your demo, and it appears in every learner's library.

Videos: MP4 with H.264/AAC plays in every browser. To convert a screen recording:
`ffmpeg -i demo.mov -c:v libx264 -crf 23 -c:a aac -movflags +faststart demo.mp4`
(`+faststart` lets playback start before the whole file downloads).

### Hot-reload development

```bash
docker compose up -d db redis
cd backend && REDIS_PASSWORD=local-redis-password COOKIE_SECURE=false LOCAL_STORAGE_DIR=../media \
  uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev       # http://localhost:5173, proxies /api
```

### Tests

```bash
docker compose up -d db redis
make test     # backend: pytest against real Postgres + Redis; frontend: vitest
make lint
```

## Configuration

All settings are environment variables (see `backend/app/config.py`). Secrets come from Vault.

| Variable | Notes |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, **`DB_PASSWORD`** | `DB_SSL=verify-ca` + `DB_CA_CERT` for Cloud SQL |
| `REDIS_HOST`, `REDIS_PORT`, **`REDIS_PASSWORD`** | `REDIS_TLS=true` + `REDIS_CA_CERT` for Memorystore |
| **`JWT_SECRET`** | also signs local-storage URLs |
| `STORAGE_BACKEND` | `local` or `gcs` (+ `GCS_BUCKET`) |
| `TRUSTED_XFF_HOPS` | `2` behind the Google load balancer, `1` behind the compose gateway |
| **`ADMIN_EMAIL`**, **`ADMIN_PASSWORD`** | first admin, created once and never overwritten |
| `COOKIE_SECURE`, `ENABLE_DOCS` | `false` locally / in prod respectively |

Bold = secret, stored in Vault.

## Repository layout

```
backend/            FastAPI app, Alembic migrations, tests, Dockerfile
frontend/           React app, nginx config with CSP, Dockerfile
scripts/            compose helpers (local gateway, test database)
.github/workflows/  CI: lint, tests, migration drift, secret + dependency + image scans
```

Coming next: the Helm chart (`charts/`) and the release workflow (push to Artifact Registry,
cosign signing, image tag bump in the `infrastructure` repo for ArgoCD).
