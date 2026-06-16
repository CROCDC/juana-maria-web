#!/usr/bin/env bash
# Build the stack and follow logs for local debugging.
set -euo pipefail

cd "$(dirname "$0")/.."

# ``up --build`` rebuilds the image and attaches to the logs of all services.
docker compose up --build
