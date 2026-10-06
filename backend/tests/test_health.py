from app.storage import is_valid_key, object_key


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200


async def test_readyz_reports_dependencies(client):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"database": "ok", "redis": "ok"}


async def test_metrics_expose_request_latency(client):
    await client.get("/api/auth/me")
    body = (await client.get("/metrics")).text
    assert (
        'http_request_duration_seconds_count{method="GET",route="/api/auth/me",status="401"}'
        in body
    )


async def test_security_headers(client):
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_object_keys_are_sanitised():
    key = object_key("0f8fad5b-d9cb-469f-a165-70867728950e", "../../etc/My Demo (1).mp4")
    assert key == "videos/0f8fad5b-d9cb-469f-a165-70867728950e/My-Demo-1-.mp4"
    assert is_valid_key(key)
    assert not is_valid_key("videos/../../etc/passwd")
