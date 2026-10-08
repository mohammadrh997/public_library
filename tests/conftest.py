import os

from dotenv import load_dotenv

load_dotenv()
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://your_app_user:your_password@localhost/library_test",
)
if "test" not in (make_url(TEST_DATABASE_URL).database or ""):
    raise RuntimeError(
        "Refusing to run: the test database name must contain 'test'. "
        "These tests delete every row in every table."
    )
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-at-least-32-bytes-long")

import httpx2
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base
from app.dependencies import get_db
from app.main import app

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def create_schema():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client():
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register_and_login(client, email, name="Tester", password="password123"):
    await client.post("/auth/register", json={"email": email, "name": name, "password": password})
    response = await client.post("/auth/token", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def member_headers(client):
    return await register_and_login(client, "member@example.com")


@pytest.fixture
async def other_member_headers(client):
    return await register_and_login(client, "other@example.com")


@pytest.fixture
async def librarian_headers(client):
    headers = await register_and_login(client, "librarian@example.com")
    async with test_engine.begin() as conn:
        await conn.execute(
            text("UPDATE members SET is_librarian = true WHERE email = 'librarian@example.com'")
        )
    return headers


@pytest.fixture
async def book(client, librarian_headers):
    response = await client.post(
        "/books",
        headers=librarian_headers,
        json={
            "title": "Dune",
            "author": "Frank Herbert",
            "isbn": "9780441013593",
            "total_copies": 2,
        },
    )
    return response.json()


@pytest.fixture
def insert_book_directly():
    async def insert(title, isbn):
        async with test_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO books (title, author, isbn, total_copies) VALUES (:t, 'A', :i, 1)"
                ),
                {"t": title, "i": isbn},
            )

    return insert
