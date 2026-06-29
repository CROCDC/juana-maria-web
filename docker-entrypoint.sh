#!/bin/sh
set -e

# Apply any pending database migrations before the app starts serving. Idempotent:
# a no-op when the DB is already at head. Runs once per container start, before
# gunicorn forks its workers, so the schema is always current by the time the app
# accepts requests. DATABASE_URL and FLASK_APP come from the environment.
python -m flask db upgrade

exec "$@"
