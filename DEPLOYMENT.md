# Server deployment

This document describes how **Wunschkonzert** runs on a Linux server with Docker Compose, **GitLab CI** deploy jobs, and **Caddy** for HTTPS.

## Architecture

- **Production** (`/opt/wunschkonzert`): **Caddy** (ports **80** / **443**), **API**, **frontend** container (pre-built images), **PostgreSQL**.
- **Staging** (`/opt/wunschkonzert-staging`): **API**, **frontend**, **PostgreSQL** only — **no** second Caddy.
- **`wunschkonzert_edge`**: shared Docker network so **production Caddy** can reverse-proxy to **staging** containers by hostname.
- Public URLs:
  - Production: `https://wunschkonzert.jj11.ch` — API under `https://wunschkonzert.jj11.ch/api/...`
  - Staging: `https://staging-wunschkonzert.jj11.ch` — same `/api` prefix pattern.

Repo files:

| Path | Role |
|------|------|
| `compose.prod.yaml` | Production stack |
| `compose.staging.yaml` | Staging stack |
| `Caddyfile` | TLS + routing (both hostnames); lives **next to** `compose.prod.yaml` |
| `compose.prod.env.example` | Template for production `.env` |
| `compose.staging.env.example` | Template for staging `.env.staging` |

## Prerequisites

- **Ubuntu** (or similar) with **Docker Engine** and **Docker Compose plugin** (`docker compose` works).
- **DNS** `A` records for both hostnames pointing at the server’s **public** IPv4 (and **AAAA** if you use IPv6).
- **Firewall**: allow **22** (SSH), **80**, **443**.
- **GitLab Container Registry** access: your project builds push `backend` / `frontend` images tagged `main` (production) and `dev` (staging).

## One-time server setup

### 1. Deploy user and directories

Use a dedicated user (e.g. `deploy`) in the `docker` group, or your own user — the same account must own the app directories and match **GitLab `DEPLOY_USER`**.

```bash
sudo mkdir -p /opt/wunschkonzert /opt/wunschkonzert-staging
sudo chown -R deploy:deploy /opt/wunschkonzert /opt/wunschkonzert-staging
```

Copy from this repository into **`/opt/wunschkonzert`**:

- `compose.prod.yaml`
- `Caddyfile`

Copy into **`/opt/wunschkonzert-staging`**:

- `compose.staging.yaml`

### 2. Environment files (never commit real secrets)

**`/opt/wunschkonzert/.env`** — see `compose.prod.env.example`:

- `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `SPOTIFY_*` if you use Spotify (see below)
- **Recommended** for manual `docker compose` on the server: set `BACKEND_IMAGE` and `FRONTEND_IMAGE` to your registry URLs with tag **`main`**.

**`/opt/wunschkonzert-staging/.env.staging`** — see `compose.staging.env.example`:

- Different `POSTGRES_PASSWORD` than production
- **`BACKEND_IMAGE`** / **`FRONTEND_IMAGE`** with tag **`dev`** (required for local compose if CI env vars are not exported)
- Staging `SPOTIFY_REDIRECT_URI` if needed

**Registry image format** (replace with your GitLab host and path; example self‑managed):

```env
BACKEND_IMAGE=registry.gitlab.ost.ch:45023/seproj/2026-fs/g15-wunschkonzert/wunschkonzert/backend:main
FRONTEND_IMAGE=registry.gitlab.ost.ch:45023/seproj/2026-fs/g15-wunschkonzert/wunschkonzert/frontend:main
```

Use **Package Registry → Container Registry** in GitLab to copy the exact path; do **not** use the `https://gitlab...` project URL.

### 3. Docker network

The shared edge network is created by deploy scripts or once manually:

```bash
docker network create wunschkonzert_edge
```

### 4. Registry login (manual pulls)

CI uses a job token; on the server you need a **Personal Access Token** or **Deploy Token** with **`read_registry`**, then:

```bash
docker login registry.example.com:port
```

## GitLab CI/CD

### Variables (project **Settings → CI/CD → Variables**)

| Variable | Description |
|----------|-------------|
| `DEPLOY_USER` | SSH account on the server |
| `DEPLOY_HOST` | SSH hostname or IP |
| `DEPLOY_SSH_PRIVATE_KEY` | SSH private key — PEM or File-type|
| `DEPLOY_PATH` | Default `/opt/wunschkonzert` |
| `DEPLOY_PATH_STAGING` | Default `/opt/wunschkonzert-staging` |
| `DEPLOY_SSH_KNOWN_HOSTS` | Optional: output of `ssh-keyscan -H -p …` if runners cannot run keyscan |

Protected variables only apply on **protected branches** — protect **`main`** and **`dev`** if deploy vars are protected.

### Pipelines

- **`main`**: pushes `:main` images (when backend/frontend change), runs **`deploy:production`**.
- **`dev`**: pushes `:dev` images, runs **`deploy:staging`**.

## Bring-up order

1. **DNS** and **firewall** ready.
2. **Production** stack must run **Caddy** (otherwise nothing listens on **443** for either hostname):

   ```bash
   cd /opt/wunschkonzert
   docker network create wunschkonzert_edge 2>/dev/null || true
   docker compose --env-file .env -f compose.prod.yaml pull
   docker compose --env-file .env -f compose.prod.yaml up -d
   ```

3. **Staging** stack:

   ```bash
   cd /opt/wunschkonzert-staging
   docker compose --env-file .env.staging -f compose.staging.yaml pull
   docker compose --env-file .env.staging -f compose.staging.yaml up -d
   ```

4. Check:

   ```bash
   docker compose -f … ps
   curl -sS https://wunschkonzert.jj11.ch/api/health
   curl -sS https://staging-wunschkonzert.jj11.ch/api/health
   ```

## Spotify OAuth

In the **Spotify Developer Dashboard**, add redirect URIs **exactly** as:

- Production: `https://wunschkonzert.jj11.ch/api/auth/spotify/callback`
- Staging: `https://staging-wunschkonzert.jj11.ch/api/auth/spotify/callback`

Set the matching **`SPOTIFY_REDIRECT_URI`** in each environment file on the server.

## Frontend API URL

- **Production/staging builds** should pass **`PUBLIC_API_URL`** / **`PUBLIC_WS_URL`** in CI (`docker:push_frontend`) so images match each host.
- The frontend client also falls back to **same-origin `/api`** in the browser when those vars are missing from the bundle, so HTTPS pages do not call `http://localhost:8000` (mixed content).
