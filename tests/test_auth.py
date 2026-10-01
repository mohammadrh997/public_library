async def test_register_returns_member_without_password(client):
    response = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "name": "New", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_cannot_grant_librarian(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "sneaky@example.com",
            "name": "S",
            "password": "password123",
            "is_librarian": True,
        },
    )
    assert response.json()["is_librarian"] is False


async def test_duplicate_email_is_rejected(client):
    payload = {"email": "dup@example.com", "name": "D", "password": "password123"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


async def test_wrong_password_and_unknown_email_look_identical(client):
    await client.post(
        "/auth/register", json={"email": "real@example.com", "name": "R", "password": "password123"}
    )
    wrong_password = await client.post(
        "/auth/token", data={"username": "real@example.com", "password": "nope-nope"}
    )
    unknown_email = await client.post(
        "/auth/token", data={"username": "ghost@example.com", "password": "nope-nope"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


async def test_me_requires_a_token(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_rejects_a_garbage_token(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_me_returns_the_logged_in_member(client, member_headers):
    response = await client.get("/auth/me", headers=member_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "member@example.com"
