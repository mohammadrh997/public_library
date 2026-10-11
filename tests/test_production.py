from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.dependencies import get_db
from app.main import app
from app.rate_limit import limiter


async def test_health_reports_503_when_the_database_is_down(client):
    dead_engine = create_async_engine(
        "postgresql+asyncpg://nobody:nothing@localhost:6391/none", poolclass=NullPool
    )
    DeadSession = async_sessionmaker(dead_engine)

    async def broken_db():
        async with DeadSession() as session:
            yield session

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/health")
    finally:
        app.dependency_overrides[get_db] = original
        await dead_engine.dispose()
    assert response.status_code == 503


async def test_login_is_rate_limited(client):
    await client.post(
        "/auth/register", json={"email": "rl@example.com", "name": "R", "password": "password123"}
    )
    limiter.reset()
    limiter.enabled = True
    try:
        codes = [
            (
                await client.post(
                    "/auth/token", data={"username": "rl@example.com", "password": "wrong-password"}
                )
            ).status_code
            for _ in range(6)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
