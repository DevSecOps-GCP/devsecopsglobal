from tests.conftest import PASSWORD, signup


async def test_signup_logs_in(client):
    user = await signup(client, "Alice@Example.com")
    assert user["email"] == "alice@example.com"
    assert user["is_admin"] is False

    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


async def test_session_cookie_is_hardened(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "full_name": "Bob", "password": PASSWORD},
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert r.headers["cache-control"] == "no-store"


async def test_duplicate_email_is_rejected_case_insensitively(client):
    await signup(client, "carol@example.com")
    r = await client.post(
        "/api/auth/signup",
        json={"email": "CAROL@example.com", "full_name": "Carol", "password": PASSWORD},
    )
    assert r.status_code == 409


async def test_short_password_is_rejected(client):
    r = await client.post(
        "/api/auth/signup", json={"email": "d@example.com", "full_name": "D", "password": "short"}
    )
    assert r.status_code == 422


async def test_login_and_logout(client):
    await signup(client, "erin@example.com")
    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401

    r = await client.post(
        "/api/auth/login", json={"email": "ERIN@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_wrong_password_and_unknown_email_look_the_same(client):
    await signup(client, "frank@example.com")
    await client.post("/api/auth/logout")
    wrong = await client.post(
        "/api/auth/login", json={"email": "frank@example.com", "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_login_is_rate_limited_per_account(client, settings):
    await signup(client, "grace@example.com")
    await client.post("/api/auth/logout")
    body = {"email": "grace@example.com", "password": "wrong-password"}
    for _ in range(settings.login_attempts_per_minute):
        assert (await client.post("/api/auth/login", json=body)).status_code == 401

    r = await client.post("/api/auth/login", json=body)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "60"
    # Even the right password is refused while limited
    body["password"] = PASSWORD
    assert (await client.post("/api/auth/login", json=body)).status_code == 429


async def test_tampered_session_is_rejected(client, settings):
    await signup(client)
    token = client.cookies[settings.cookie_name]
    client.cookies.set(settings.cookie_name, token[:-4] + "AAAA")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_anonymous_cannot_list_videos(client):
    assert (await client.get("/api/videos")).status_code == 401
