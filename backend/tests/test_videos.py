from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.main import create_app
from tests.conftest import _client, signup

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40  # ~10 KB fake mp4


async def upload_video(admin_client, title="DevSecOps on GKE", publish=True) -> dict:
    r = await admin_client.post(
        "/api/admin/videos",
        json={
            "title": title,
            "description": "Assessment demo",
            "filename": "My Demo (final).mp4",
            "content_type": "video/mp4",
            "size_bytes": len(VIDEO_BYTES),
        },
    )
    assert r.status_code == 201, r.text
    ticket = r.json()
    assert ticket["video"]["status"] == "pending"

    # The browser PUTs straight to the signed URL (GCS in prod, /api/media locally)
    r = await admin_client.put(ticket["upload_url"], content=VIDEO_BYTES, headers=ticket["headers"])
    assert r.status_code == 201, r.text

    video_id = ticket["video"]["id"]
    r = await admin_client.post(f"/api/admin/videos/{video_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"
    assert r.json()["size_bytes"] == len(VIDEO_BYTES)

    if publish:
        r = await admin_client.patch(f"/api/admin/videos/{video_id}", json={"is_published": True})
        assert r.status_code == 200
    return r.json()


async def test_regular_users_cannot_use_admin_api(user_client):
    assert (await user_client.get("/api/admin/videos")).status_code == 403
    r = await user_client.post(
        "/api/admin/videos",
        json={"title": "x", "filename": "x.mp4", "content_type": "video/mp4", "size_bytes": 1},
    )
    assert r.status_code == 403


async def test_upload_publish_and_watch(admin_client, user_client):
    video = await upload_video(admin_client)

    r = await user_client.get("/api/videos")
    assert r.status_code == 200
    assert [v["id"] for v in r.json()] == [video["id"]]

    r = await user_client.get(f"/api/videos/{video['id']}")
    assert r.status_code == 200
    playback = r.json()
    assert playback["views"] == 1

    # The player seeks with Range requests
    r = await user_client.get(playback["url"], headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert r.content == VIDEO_BYTES[:100]

    await user_client.get(f"/api/videos/{video['id']}")
    listed = (await user_client.get("/api/videos")).json()
    assert listed[0]["views"] == 2


async def test_unpublished_videos_are_hidden_from_users(admin_client, user_client):
    video = await upload_video(admin_client, publish=False)
    assert (await user_client.get("/api/videos")).json() == []
    assert (await user_client.get(f"/api/videos/{video['id']}")).status_code == 404
    # Admins can preview before publishing
    assert (await admin_client.get(f"/api/videos/{video['id']}")).status_code == 200


async def test_catalog_cache_is_invalidated_on_change(admin_client, user_client):
    video = await upload_video(admin_client)
    assert len((await user_client.get("/api/videos")).json()) == 1  # now cached

    await admin_client.patch(f"/api/admin/videos/{video['id']}", json={"is_published": False})
    assert (await user_client.get("/api/videos")).json() == []


async def test_cannot_publish_before_upload_completes(admin_client):
    r = await admin_client.post(
        "/api/admin/videos",
        json={"title": "t", "filename": "t.mp4", "content_type": "video/mp4", "size_bytes": 10},
    )
    video_id = r.json()["video"]["id"]
    r = await admin_client.patch(f"/api/admin/videos/{video_id}", json={"is_published": True})
    assert r.status_code == 409
    assert (await admin_client.post(f"/api/admin/videos/{video_id}/complete")).status_code == 409


async def test_rejects_non_video_uploads(admin_client):
    r = await admin_client.post(
        "/api/admin/videos",
        json={"title": "t", "filename": "evil.html", "content_type": "text/html", "size_bytes": 10},
    )
    assert r.status_code == 415


async def test_signed_urls_cannot_be_tampered_with(admin_client, user_client):
    video = await upload_video(admin_client)
    url = (await user_client.get(f"/api/videos/{video['id']}")).json()["url"]
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # Extending the expiry invalidates the signature
    forged = f"{parsed.path}?exp={int(qs['exp'][0]) + 3600}&sig={qs['sig'][0]}"
    assert (await user_client.get(forged)).status_code == 403
    # A download signature can't be reused to upload
    assert (await user_client.put(url, content=b"overwrite")).status_code == 403


async def test_delete_removes_video(admin_client, user_client):
    video = await upload_video(admin_client)
    assert (await admin_client.delete(f"/api/admin/videos/{video['id']}")).status_code == 204
    assert (await user_client.get("/api/videos")).json() == []
    assert (await admin_client.get("/api/admin/videos")).json() == []


async def test_app_keeps_working_when_redis_is_down(app):
    """Redis is a cache: losing it degrades performance, not availability."""
    broken = create_app(Settings(redis_port=1, redis_timeout_seconds=0.2))
    async with broken.router.lifespan_context(broken), _client(broken) as c:
        await signup(c)
        assert (await c.get("/api/videos")).status_code == 200
        assert (await c.get("/readyz")).json() == {"database": "ok", "redis": "degraded"}
