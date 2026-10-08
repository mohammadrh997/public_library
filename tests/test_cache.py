import pytest

from app.cache import create_redis_client, get_cache
from app.main import app


@pytest.fixture
async def redis_cache():
    client = create_redis_client("redis://localhost:6379/15")
    await client.flushdb()
    app.dependency_overrides[get_cache] = lambda: client
    yield client
    app.dependency_overrides.pop(get_cache, None)
    await client.flushdb()
    await client.aclose()


async def test_second_read_is_served_from_the_cache(client, redis_cache, insert_book_directly):
    await insert_book_directly("First", "1111111111")
    first = await client.get("/books")
    assert [b["title"] for b in first.json()] == ["First"]

    await insert_book_directly("Second", "2222222222")
    second = await client.get("/books")
    assert [b["title"] for b in second.json()] == ["First"]


async def test_adding_a_book_through_the_api_invalidates_the_cache(
    client, redis_cache, librarian_headers
):
    await client.get("/books")
    await client.post(
        "/books",
        headers=librarian_headers,
        json={"title": "Fresh", "author": "A", "isbn": "3333333333", "total_copies": 1},
    )
    response = await client.get("/books")
    assert [b["title"] for b in response.json()] == ["Fresh"]


async def test_the_api_still_works_when_redis_is_down(client, insert_book_directly):
    unreachable = create_redis_client("redis://localhost:6390/0")
    app.dependency_overrides[get_cache] = lambda: unreachable
    try:
        await insert_book_directly("Survivor", "4444444444")
        response = await client.get("/books")
        assert response.status_code == 200
        assert [b["title"] for b in response.json()] == ["Survivor"]
    finally:
        app.dependency_overrides.pop(get_cache, None)
        await unreachable.aclose()
