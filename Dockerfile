FROM python:3.11-slim

WORKDIR /app

# System deps: gcc/python3-dev to build some wheels (e.g. psycopg2); git to fetch the
# private flask-sitecopy dependency from GitHub during pip install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# flask-sitecopy lives in a PRIVATE GitHub repo, so pip needs a credential to clone it.
# It is passed as a BuildKit build secret (id=github_token), NOT an ARG/ENV, so the
# token never lands in an image layer or the build history. The git credential config
# and the token both live only for this RUN (tmpfs mount + config removed in the same
# layer). If the secret is absent, the token is empty and the private clone fails with a
# clear auth error — provide it (see docker-compose.yml / Jenkinsfile).
RUN --mount=type=secret,id=github_token \
    if [ -s /run/secrets/github_token ]; then \
      git config --global \
        url."https://$(cat /run/secrets/github_token)@github.com/".insteadOf \
        "https://github.com/"; \
    fi; \
    pip install --no-cache-dir -r requirements.txt; \
    status=$?; \
    rm -f /root/.gitconfig; \
    exit $status

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
