# Vercel deploy

The site runs as a single Vercel Function (Python/WSGI) fronted by Vercel's CDN,
deployed from GitHub Actions — the same shape as `mg-nautica-wix`. This document
covers the pieces that are specific to a Flask app.

`velaclasica.ar` has been cut over to Vercel (2026-09-02). The local-server deploy
(`Jenkinsfile`, `docker-compose.yml`, `.github/workflows/deploy.yml`) is still wired and
still redeploys on every push to `main` — kept as a rollback target until Vercel has run
production long enough to trust. See [After the cutover](#after-the-cutover).

## What runs where

| Concern | Local server (today) | Vercel |
|---|---|---|
| App | gunicorn in Docker | one Vercel Function (`wsgi.py`) |
| Static assets | Flask, from `public/static` | CDN, from `public/static` |
| Database | Postgres container | Neon (Vercel Marketplace) |
| Editor uploads | `LocalFileStore` on a volume | Vercel Blob (`app/media_store.py`) |
| Migrations | `docker-entrypoint.sh` at boot | GitHub Actions, before the prod deploy |
| Metrics / logs | Prometheus + Loki | Vercel observability only |

### Entrypoint

Vercel's Flask preset loads a top-level `app` from a fixed set of filenames;
`wsgi.py` is the one this repo uses. `run.py` stays for Docker — its Prometheus and
psutil instrumentation only makes sense for a long-lived process.

### Static assets

The assets live in `public/static/` — not `app/static/`, which is where the rest of
the house style puts them. Vercel serves `public/**` from its CDN and falls through
to the function only for paths that are not there, so `/static/...` URLs are unchanged
and never reach Python. Flask's `static_folder` points at the same directory, so Docker
and local dev serve the identical tree.

Two things follow from `public/` being served by the CDN but **left out of the function
bundle**, both verified against a real deployment:

- `app/content/image_manifest.json` holds the intrinsic sizes and variant widths of the
  photos. It lives inside the package, not next to the images it describes, because a
  manifest the function cannot read degrades every `<picture>` to the macro's guessed
  dimensions — wrong `width`/`height` (layout shift) and a missing 1920w candidate.
- The `?v=` cache-buster cannot use file mtimes there. On Vercel it falls back to the
  deployment id (`_static_version` in `app/factory.py`); everywhere else the per-file
  mtime is used exactly as before. Without it, `immutable` would pin a returning
  visitor to the previous deploy's CSS for a year.

A build command that generates `public/` does **not** work: Vercel collects the static
files from the uploaded source, before the build runs.

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

2. **Provision Postgres** with `vercel integration add neon` (accepting the marketplace
   terms in the browser is a one-time manual step). Attaching it injects `DATABASE_URL`
   (Neon's pooled endpoint) and `DATABASE_URL_UNPOOLED` (the direct one).

   Then give the database a `search_path`, **once**, over the unpooled endpoint:

   ```sql
   ALTER DATABASE neondb SET search_path = "$user", public;
   ALTER ROLE neondb_owner SET search_path = "$user", public;
   ```

   A fresh Neon database hands the pooler an **empty** `search_path`, so every
   unqualified query (`select … from site_texts`) fails with `relation does not exist`
   while the direct endpoint works fine — migrations succeed and the app then 500s.
   Neon's pooler rejects `options=-c search_path=…` at connection startup, so this
   cannot be fixed from `SQLALCHEMY_ENGINE_OPTIONS`; the database-level default is the
   fix, and PgBouncer's backends pick it up when they start. **Re-apply it if the
   database is ever re-provisioned** — nothing in this repo can.

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
   gh secret set MIGRATIONS_DATABASE_URL   # DATABASE_URL_UNPOOLED, for `flask db upgrade`
   ```

## How a deploy works

- **`ci.yml`** — mypy plus the pytest suite (testcontainers Postgres + Playwright) on
  every push and PR. Set it as a required check on `main`.
- **`vercel.yml`** — PR → Preview, `main` → Production. The production path runs
  `flask db upgrade` against `MIGRATIONS_DATABASE_URL` before deploying; previews do not,
  because they share the production database and would move the schema ahead of the live
  code.

## DNS cutover

`velaclasica.ar` is on Cloudflare. Before the cutover both the apex and `www` were
proxied CNAMEs to the Cloudflare Tunnel that reaches the Pi:

```
CNAME velaclasica.ar      392770c8-a3e4-4b8e-8899-5b76b552b737.cfargotunnel.com  (proxied)
CNAME www.velaclasica.ar  392770c8-a3e4-4b8e-8899-5b76b552b737.cfargotunnel.com  (proxied)
```

They now point at Vercel, **DNS only** (grey cloud) — Vercel terminates TLS, and leaving
Cloudflare's proxy in front puts a second terminator in the path and breaks certificate
issuance:

```
CNAME velaclasica.ar      52170ddcd5d22574.vercel-dns-017.com   (DNS only, TTL 60)
CNAME www.velaclasica.ar  52170ddcd5d22574.vercel-dns-017.com   (DNS only, TTL 60)
```

A CNAME at the apex works because Cloudflare flattens it; it is also the target Vercel
itself recommends (`GET /v6/domains/<domain>/config` → `recommendedCNAME`). The TTL is
deliberately low so a rollback takes effect quickly.

**Issue the certificate before repointing the apex.** Vercel does not pre-issue for a
domain whose DNS still points elsewhere, so a naive flip leaves the site without HTTPS
until issuance completes. The DNS-01 challenge avoids that entirely:

```bash
vercel certs issue velaclasica.ar --challenge-only   # prints the _acme-challenge TXT
# add that TXT record in Cloudflare, wait for it to resolve
vercel certs issue velaclasica.ar                    # cert exists before any traffic moves
# now repoint the record, and delete the TXT afterwards
```

**Rollback** is the same edit in reverse: both records back to the `cfargotunnel.com`
target above, proxied. The Docker stack on the Pi keeps running and keeps redeploying
from `main`, so the old site stays one DNS change away.

## After the cutover

**Still pending.** Once Vercel has served production for long enough to trust it, remove
the local-server deploy: `Jenkinsfile`, `Dockerfile*`, `docker-compose.yml`, `docker-entrypoint.sh`,
`promtail.yml`, `.github/workflows/deploy.yml`, and the `prometheus_flask_exporter` /
`psutil` / `gunicorn` requirements with `run.py`. Then `docker compose down -v` on the
Pi and delete the Jenkins job.
