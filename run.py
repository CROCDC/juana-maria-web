import os

import psutil
from prometheus_client import Gauge
from prometheus_flask_exporter import PrometheusMetrics

from app import app

# Expose /metrics for Prometheus, plus a couple of process gauges.
metrics = PrometheusMetrics(app)

_process = psutil.Process(os.getpid())

process_memory_bytes = Gauge(
    "app_process_memory_bytes", "Resident memory of the app process in bytes"
)
process_cpu_percent = Gauge(
    "app_process_cpu_percent", "CPU usage of the app process as a percentage"
)


@process_memory_bytes.set_function
def _collect_memory() -> float:
    return float(_process.memory_info().rss)


@process_cpu_percent.set_function
def _collect_cpu() -> float:
    return float(_process.cpu_percent(interval=None))


if __name__ == "__main__":
    # Debug on by default for local ``python run.py``; the Docker image and
    # compose set FLASK_DEBUG=0 so production stays out of debug mode.
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False", "")
    app.run(host="0.0.0.0", port=7017, debug=debug)
