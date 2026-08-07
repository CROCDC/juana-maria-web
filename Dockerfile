FROM python:3.11-slim

WORKDIR /app

# System deps needed to build some Python wheels (e.g. psycopg2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

ENV FLASK_APP=run.py
ENV FLASK_DEBUG=0

EXPOSE 7017

# Run pending DB migrations (flask db upgrade) before starting the server; see
# docker-entrypoint.sh. The entrypoint then execs the CMD below.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Production WSGI server. Werkzeug's dev server is single-threaded and unhardened;
# gunicorn reads its target from ``run:app`` (the module-level app in run.py).
CMD ["gunicorn", "--bind", "0.0.0.0:7017", "--workers", "2", "--threads", "4", "run:app"]
