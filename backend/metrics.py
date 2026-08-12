"""Low-cardinality Prometheus metrics for the HTTP boundary."""

from __future__ import annotations

from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


REQUESTS = Counter("vr_http_requests_total", "HTTP requests", ("method", "route", "status"))
LATENCY = Histogram("vr_http_request_duration_seconds", "HTTP request duration", ("method", "route"))
IN_PROGRESS = Gauge("vr_http_requests_in_progress", "HTTP requests currently executing")
DEPENDENCY_READY = Gauge("vr_dependency_ready", "Dependency readiness", ("dependency",))


async def metrics_middleware(request: Request, call_next):
    started = perf_counter()
    IN_PROGRESS.inc()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        REQUESTS.labels(request.method, route_path, str(status_code)).inc()
        LATENCY.labels(request.method, route_path).observe(perf_counter() - started)
        IN_PROGRESS.dec()


def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
