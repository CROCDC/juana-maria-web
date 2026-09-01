# Vercel deploy

The site runs as a single Vercel Function (Python/WSGI) fronted by Vercel's CDN,
deployed from GitHub Actions — the same shape as `mg-nautica-wix`. This document
covers the pieces that are specific to a Flask app.

Until the DNS cutover the local-server deploy (`Jenkinsfile`, `docker-compose.yml`,
`.github/workflows/deploy.yml`) stays alive and keeps serving `velaclasica.ar`.

## What runs where

| Concern | Local server (today) | Vercel |
|---|---|---|
| App | gunicorn in Docker | one Vercel Function (`wsgi.py`) |
| Static assets | Flask, from `app/static` | CDN, from `public/static` |
| Database | Postgres container | Neon (Vercel Marketplace) |
| Editor uploads | `LocalFileStore` on a volume | Vercel Blob (`app/media_store.py`) |
| Migrations | `docker-entrypoint.sh` at boot | GitHub Actions, before the prod deploy |
| Metrics / logs | Prometheus + Loki | Vercel observability only |

### Entrypoint

Vercel's Flask preset loads a top-level `app` from a fixed set of filenames;
`wsgi.py` is the one this repo uses. `run.py` stays for Docker — its Prometheus and
psutil instrumentation only makes sense for a long-lived process.

### Static assets

`vercel.json`'s `buildCommand` copies `app/static` into `public/static` at build
time. Vercel serves `public/**` from the CDN and only falls through to the function
for paths that do not exist there, so `/static/...` URLs are unchanged and never
touch Python. `app/static` also stays in the function bundle: `app/factory.py` reads
`img/manifest.json` from it to build the responsive `<picture>` sets, and stats each
file for the `?v=` cache-buster.

`public/` is generated, not committed.

### Uploads

A function's filesystem is read-only, so `VercelBlobFileStore` (`app/media_store.py`)
replaces sitecopy's `LocalFileStore` whenever `BLOB_READ_WRITE_TOKEN` is present.
Naming is content-addressed exactly as before, so a re-upload is idempotent. With the
variable unset — dev, Docker — the local store is used and nothing changes.

## One-time setup

1. **Link the project**

   ```bash
   npm i -g vercel@latest
   vercel login
   vercel link            # creates .vercel/project.json (gitignored)
   ```

2. **Provision Postgres.** Vercel dashboard → Storage → Neon. Attaching it to the
   project injects `DATABASE_URL` automatically. Use the **pooled** connection string.

3. **Provision Blob.** Vercel dashboard → Storage → Blob. Attaching it injects
   `BLOB_READ_WRITE_TOKEN`.

4. **Set the remaining environment variables** (Production and Preview):

   ```bash
   vercel env add SECRET_KEY production
   vercel env add ADMIN_PASSWORD production
   vercel env add CANONICAL_URL production        # https://velaclasica.ar
   vercel env add REDIRECT_HOSTS production       # www.velaclasica.ar
   vercel env add UMAMI_WEBSITE_ID production     # b5d4b173-a160-49f5-8f0d-076e804d0007
   vercel env add FLASK_DEBUG production           # 0
   ```

   `SECRET_KEY` and `ADMIN_PASSWORD` must match the values Infisical serves to the
   Docker deploy, or admin sessions break at the cutover.

5. **Migrate the data** from the local server (small: a handful of rows):

   ```bash
   ssh ssh.nexttech.com.ar \
     'docker exec juana-maria-web-db pg_dump -U juana_maria_web -d juana_maria_web \
        --data-only --no-owner --no-privileges' > juana-maria-data.sql
   psql "$NEON_DATABASE_URL" -f juana-maria-data.sql
   ```

   Run the migrations first (`FLASK_APP=wsgi.py flask db upgrade`) so the schema exists.

6. **Wire GitHub Actions.** Turn **off** Vercel's own Git integration for the project
   so deploys happen only from Actions, then:

   ```bash
   gh variable set DEPLOY_ENABLED --body true
   gh secret set VERCEL_TOKEN        # vercel.com/account/tokens
   gh secret set VERCEL_ORG_ID       # from .vercel/project.json
   gh secret set VERCEL_PROJECT_ID   # from .vercel/project.json
   gh secret set DATABASE_URL        # the Neon connection string
   ```

## How a deploy works

- **`ci.yml`** — mypy plus the pytest suite (testcontainers Postgres + Playwright) on
  every push and PR. Set it as a required check on `main`.
- **`vercel.yml`** — PR → Preview, `main` → Production. The production path runs
  `flask db upgrade` against `DATABASE_URL` before deploying; previews do not, because
  they share the production database and would move the schema ahead of the live code.

## DNS cutover

`velaclasica.ar` is on Cloudflare, currently proxied to the Cloudflare Tunnel that
reaches the Pi. To move it:

1. Add the domain in the Vercel project (Settings → Domains) — both apex and `www`.
2. In Cloudflare DNS replace the tunnel records with what Vercel asks for
   (`A 76.76.21.21` on the apex, `CNAME cname.vercel-dns.com` on `www`) and set them
   to **DNS only** (grey cloud). Vercel terminates TLS itself; keeping the orange
   cloud puts a second proxy in front of it and breaks certificate issuance.
3. Wait for Vercel to report the certificate as issued, then check both hosts.

**Rollback** is the same edit in reverse: point the records back at the tunnel. The
Docker stack on the Pi keeps running throughout, so the old site is always one DNS
change away.

## After the cutover

Once Vercel has served production for long enough to trust it, remove the local-server
deploy: `Jenkinsfile`, `Dockerfile*`, `docker-compose.yml`, `docker-entrypoint.sh`,
`promtail.yml`, `.github/workflows/deploy.yml`, and the `prometheus_flask_exporter` /
`psutil` / `gunicorn` requirements with `run.py`. Then `docker compose down -v` on the
Pi and delete the Jenkins job.
