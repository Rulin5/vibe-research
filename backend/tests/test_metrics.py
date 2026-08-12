from fastapi import FastAPI
from fastapi.testclient import TestClient

from metrics import metrics_endpoint, metrics_middleware


def test_metrics_expose_low_cardinality_http_series():
    app = FastAPI()
    app.middleware("http")(metrics_middleware)
    app.add_api_route("/api/metrics", metrics_endpoint, methods=["GET"])

    @app.get("/api/items/{item_id}")
    def item(item_id: str):
        return {"item_id": item_id}

    client = TestClient(app)
    assert client.get("/api/items/private-user-123").status_code == 200
    metrics = client.get("/api/metrics").text

    assert "vr_http_requests_total" in metrics
    assert "/api/items/{item_id}" in metrics
    assert "private-user-123" not in metrics


def test_metrics_do_not_include_query_strings():
    app = FastAPI()
    app.middleware("http")(metrics_middleware)
    app.add_api_route("/api/metrics", metrics_endpoint, methods=["GET"])

    @app.get("/api/search")
    def search():
        return {"ok": True}

    client = TestClient(app)
    client.get("/api/search?api_key=must-not-leak")

    assert "must-not-leak" not in client.get("/api/metrics").text
