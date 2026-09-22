# Monitoring and alerts

Alerts go by mail to `ALERT_EMAIL_TO` through [Resend](https://resend.com). Nothing
here pages anybody; the goal is that a production failure stops depending on somebody
opening the site.

## Why this exists

On **2026-09-21** Neon's free-plan quota suspended the database. Every request that
touched Postgres 500'd — the seven topic pages, `/sitemap.xml` and the whole `/admin`
— for hours, with no signal anywhere:

```
Exception on /admin [GET]
  psycopg2.OperationalError: connection to server at "…-pooler.…neon.tech" failed:
  ERROR:  Your account or project has exceeded the quota. Upgrade your plan…
```

Two things made it invisible. The runtime logs held the whole story but they live on
Vercel, are short-lived, and nobody reads logs they are not already worried about. And
`/` kept answering **200** — it was the one read with a net — so any uptime check
pointed at the home page would have reported the site healthy the entire time.

## The three signals

| Signal | Where it runs | What it catches | Latency |
|---|---|---|---|
| Unhandled exception | the app (`app/alerts.py`) | anything that 500s a real request, with the traceback | immediate, while there is traffic |
| Synthetic check | GitHub Actions (`.github/workflows/monitor.yml`) | the site being down with nobody on it, including a deploy that cannot boot | 15 min (shallow) / 1 h (deep) |
| Pipeline failure | `ci.yml` / `vercel.yml` → `alert.yml` | a red CI on `main`, a failed production deploy | immediate |

### Unhandled exceptions

`install_error_alerts()` hooks Flask's `got_request_exception`, so the visitor's
response is untouched and the original exception — not the `InternalServerError`
wrapper — is what gets mailed.

Mails are throttled per `ALERT_THROTTLE_SECONDS` (default 900) keyed on the exception
type plus the frame that raised it, **not** on the URL: a database outage raises the
same error from every route, and keying on the URL would mail once per page. The
throttle lives in the function instance's memory, so Vercel running several instances
multiplies it — the bound is "a handful per outage", not exactly one.

### Synthetic checks

`scripts/monitor.py`, stdlib-only and self-contained on purpose: importing the app
package would drag in Flask, SQLAlchemy and a `DATABASE_URL`, and would make the
watchdog fail for the same reasons as the thing it watches.

- **Shallow** (`*/15`) — `/healthz?db=0` plus the public pages. Cheap: those pages are
  served by the CDN and never reach Postgres.
- **Deep** (hourly) — `/healthz` with a real database round-trip, plus Neon's quota.

The two frequencies are not an accident. **A Neon compute stays awake for five minutes
after each query**, so a deep poll every 15 minutes would keep the database running
about a third of the time — roughly 60 of the free plan's 100 CU-hours a month. The
watchdog would be causing the outage it is there to catch.

Up/down state rides in the Actions cache (`.monitor-state`), so an outage mails once
and recovery mails once, instead of every 15 minutes for as long as it lasts.

### Neon quota

The deep run reads `GET /projects/{id}` and `/branches` from Neon's API and warns at
`NEON_QUOTA_WARN_PCT` (default 80%) of each free-plan allowance. Those allowances are
configuration here, not something the API returns — its `quota` object only holds
limits somebody set by hand.

| Free plan, per project | Default limit used here |
|---|---|
| Compute | `NEON_COMPUTE_HOURS_LIMIT` = 100 CU-hours/month |
| Storage | `NEON_STORAGE_GB_LIMIT` = 0.5 GB |
| Transfer | `NEON_TRANSFER_GB_LIMIT` = 5 GB/month |

Compute and transfer reset with the billing period; storage is a standing limit.

## Keeping the database out of the quota

The alert tells you the quota is about to blow; it does not stop it. What does is
keeping traffic off the function, because **every HTML render queries Postgres**
(sitecopy's texts, plus topic visibility) and every query buys another five minutes of
awake compute — Neon's scale-to-zero delay is fixed at five minutes and cannot be
lowered. With crawlers hitting the site around the clock, an origin that renders on
every request simply never lets the database sleep.

So public HTML is cached at Vercel's CDN (`add_cdn_cache_headers`, `app/factory.py`):

```
Cache-Control:            public, max-age=0, must-revalidate
CDN-Cache-Control:        public, s-maxage=86400, stale-while-revalidate=604800
Vercel-CDN-Cache-Control: public, s-maxage=86400, stale-while-revalidate=604800
Vercel-Cache-Tag:         site-html
```

Three headers because they answer three different caches, and the split is not
cosmetic. **`Cache-Control` alone did not work.** With `max-age=0` sitting next to
`s-maxage` in the one header, production stayed `x-vercel-cache: MISS` on every single
request — while static files on the same domain cached normally, which is what proved
the problem was the header and not the CDN. `Vercel-CDN-Cache-Control` takes precedence
for Vercel's cache, so the browser keeps its `max-age=0` (revalidate every time)
without that zero having any say over the shared copy.

- `s-maxage` (`CDN_CACHE_SECONDS`) — how long the CDN serves without asking the
  function. This is the dial that decides the Neon bill.
- `stale-while-revalidate` (`CDN_STALE_SECONDS`) — nobody ever waits for a refresh.
- `Vercel-Cache-Tag` — what a save purges. See below.

The header is skipped entirely for `/admin`, for a logged-in admin, for `?edit=` and
`?preview=` URLs, and for a page rendered while Postgres was unreachable — its nav,
and whether it should exist at all, is a guess that would outlive the outage.

### The `Vary: Cookie` trap

**Vercel caches nothing whose `Vary` names `Cookie`.** It treats it as a
high-cardinality header, serves the response normally, and records `Vary key denied`
in the runtime logs. The first version of this caching shipped with `Vary: Cookie` set
deliberately, so between 2026-09-21 and 2026-09-22 the hit rate was exactly zero:
every visit reached the function and woke Postgres, which is the opposite of the point.

Removing our own header is not enough. **Flask adds `Vary: Cookie` by itself** the
moment anything reads the session, and flask-sitecopy checks `is_logged_in` on every
public render — and it adds it in `save_session`, which runs *after* every
`after_request`, so it cannot be stripped from there. `CacheableSessionInterface`
(`app/factory.py`) overrides that method and drops the header from responses that
already carry `Vercel-Cache-Tag` — the tag being the record of the app having decided
the bytes do not depend on the cookie.

### Checking it still works

The only proof is production. `x-vercel-cache` must reach `HIT` on a repeat request:

```bash
for i in 1 2 3; do curl -sI https://velaclasica.ar/ | grep -i x-vercel-cache; done
```

If it is `MISS` every time, the caching is doing nothing at all and every visit is
waking Postgres. Two causes have already cost a day each: a `Vary` naming `Cookie`,
and `s-maxage` carried only in `Cache-Control`. Compare against a static asset —
`/static/css/admin.css` should `HIT` on the second request. If the static file caches
and the page does not, the problem is in the page's headers, not the CDN.

### Purging on write

A long `s-maxage` and a working content editor are in direct conflict: the edit sits
behind the cache until it expires. `purge_cdn_after_admin_write` resolves it — any
successful non-GET under `/admin` (except signing in and out) calls
`invalidate_site_cache()` (`app/cdn.py`), which marks the tag stale through
`POST /v1/edge-cache/invalidate-by-tags`. Invalidate, not delete: the next visitor is
served the stale copy instantly while the refresh happens behind them.

It hangs off the request rather than a save hook because the editor's writes belong to
flask-sitecopy, which exposes none — and this way a topic toggle, a copy edit and an
image upload are all covered by one rule.

With `VERCEL_PURGE_TOKEN` set, raising `CDN_CACHE_SECONDS` costs nothing but a longer
wait for the rare visitor who is mid-page when an edit lands. Without it, the purge is
a logged no-op and `CDN_CACHE_SECONDS` is the full staleness window — which is why the
default stays at an hour.

### What a render still costs

`published_state()` is memoised per request, so the nav and the view share one SELECT
instead of two. Seeding no longer runs at import: it used to open a connection on
every cold start, waking the compute for five minutes even to serve a request that
needed no data, and it is only ever useful against an empty table.

## Surviving the outage instead of reporting it

The outage was asymmetric for no good reason: `/` degraded, the seven topic pages and
`/sitemap.xml` 500'd. They all read the same seven booleans.

`TopicVisibilityRepository` now splits the two needs:

- **`published_state()`** — what the public is shown. On a database error it falls
  back to the last map this process read successfully, and then to `DEFAULT_ENABLED`
  if it never read one (a cold start mid-outage). Used by the topic views, the crew
  form, the sitemap and the nav. It also reports whether the answer is
  `authoritative`, because a guess must not be served as a 404: a page the fallback
  thinks is unpublished answers **503 + `Retry-After`**, which tells Google to come
  back rather than to drop the URL.
- **`get_state_map()`** — unchanged, still raises. The admin panel writes, and a panel
  showing a stale map is somebody toggling a row that is not the row they see.

The trade-off is deliberate and worth saying out loud: **a topic switched off can
reappear while the database is down.** That beats 500ing the whole site, but it is a
real consequence — if some topic must never be publicly reachable, visibility is the
wrong mechanism for it.

Measured against the live, quota-suspended database, that turns this:

| | before | after |
|---|---|---|
| `/` | 200 (empty nav) | 200 |
| `/crew-program` | **500** | 200 |
| `/sitemap.xml` | **500** | 200 |
| `/routes`, `/historic-sailings`, … | **500** | 503 + `Retry-After` |
| `/admin` | 500, silently | 500, and it mails |

So during the next outage the public site stays up, the admin breaks loudly, and the
mail goes out. That is the intended shape.

## Configuration

Secrets live in the Vercel project (for the app) and in the repo (for Actions).

| Name | Where | What |
|---|---|---|
| `RESEND_API_KEY` | Vercel env + GitHub **secret** | Resend API key |
| `ALERT_EMAIL_TO` | Vercel env + GitHub **variable** | recipients, comma-separated |
| `ALERT_EMAIL_FROM` | Vercel env + GitHub **variable** | a sender on a domain verified in Resend, or `onboarding@resend.dev` |
| `ALERT_THROTTLE_SECONDS` | Vercel env (optional) | default 900 |
| `CDN_CACHE_SECONDS` | Vercel env (optional) | default 3600; `0` disables CDN caching |
| `VERCEL_PURGE_TOKEN` | Vercel env | a Vercel token with cache-purge rights; without it a save cannot clear the CDN |
| `VERCEL_PROJECT_ID` | Vercel env | the project the purge targets |
| `VERCEL_TEAM_ID` | Vercel env | `team_P9lSJA4rEEdw6QU6DWiolk6Y` (vela-clasica) |
| `CDN_STALE_SECONDS` | Vercel env (optional) | default 86400 |
| `NEON_API_KEY` | GitHub **secret** | from the Neon console; the quota check is skipped without it |
| `NEON_PROJECT_ID` | GitHub **variable** | also injected into Vercel by the integration |

```bash
# Vercel (production)
vercel env add RESEND_API_KEY production
vercel env add ALERT_EMAIL_TO production
vercel env add ALERT_EMAIL_FROM production

# GitHub Actions
gh secret set RESEND_API_KEY
gh secret set NEON_API_KEY
gh variable set ALERT_EMAIL_TO   --body 'crocdc1999@gmail.com'
gh variable set ALERT_EMAIL_FROM --body 'alertas@velaclasica.ar'
gh variable set NEON_PROJECT_ID  --body 'gentle-silence-96921676'
```

### Starting without a verified domain

`ALERT_EMAIL_FROM=onboarding@resend.dev` is Resend's shared sandbox sender and needs
no DNS at all, but it only delivers **to the address the Resend account was opened
with**; anything else comes back `403 validation_error`. Since the one recipient here
is the account owner, that is a working configuration, not a stopgap — verify
`velaclasica.ar` in Resend when the alerts should come from the site's own domain, or
when a second recipient is added.

Everything degrades to a no-op when unset: `send_alert()` logs a warning and returns
`False`, and the quota check prints that it was skipped. The site never fails because
alerting is not configured.

## Trying it

```bash
gh workflow run monitor.yml -f deep=true      # a full run, mail included
python scripts/monitor.py --deep              # locally; needs the env above
curl -s https://velaclasica.ar/healthz | jq   # what the watchdog reads
vercel logs https://velaclasica.ar            # the logs behind an alert
```

A `503` from `/healthz` is the endpoint working. It reports the failure in
`checks.db`; it does not raise, so it never mails on its own — the watchdog decides.
