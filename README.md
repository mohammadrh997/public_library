# Public Library Lending API

[![CI](https://github.com/mohammadrh997/public_library/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammadrh997/public_library/actions/workflows/ci.yml)

A REST API for a library: librarians manage the catalogue, members borrow and return books.

**Live:** https://public-library-pwmb.onrender.com/docs
Free tier: after 15 minutes idle, the first request takes about 45 seconds while the service wakes up; later requests take about 0.3 seconds.

## Highlights

- JWT authentication with two roles, member and librarian, checked per resource
- Borrowing rules enforced server-side: no free copies, no duplicate loans, only your own returns
- Book list cached in Redis, with `ETag` / `304` on book details; the API keeps working if Redis is down
- Login rate limited, and timed so it does not reveal which emails are registered
- 47 tests against a real PostgreSQL database, plus Ruff, mypy, and migration checks in CI
- Every change reaches `main` through a pull request that must pass CI; Render deploys `main` automatically

**Stack:** FastAPI · async SQLAlchemy 2.0 · PostgreSQL · Alembic · Pydantic v2 · Redis · pytest · Docker · GitHub Actions · Render + Neon

## Run it locally

You need Docker.

```bash
git clone https://github.com/mohammadrh997/public_library.git
cd public_library
cp .env.example .env
```

Set `SECRET_KEY` in `.env`, for example with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Then:

```bash
docker compose up --build
```

The API runs at http://localhost:8000/docs, with PostgreSQL on `localhost:5433` and Redis on `localhost:6379`.

Registration always creates a member. To make one a librarian:

```bash
docker compose exec db psql -U library -d library -c "UPDATE members SET is_librarian = true WHERE email = 'you@example.com';"
```

## Run the tests

Create the test database once, then run pytest against it:

```bash
docker compose exec db psql -U library -d library -c "CREATE DATABASE library_test;"
pip install -r requirements.txt -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+asyncpg://library:library@localhost:5433/library_test pytest -q
```

In PowerShell, set the variable with `$env:TEST_DATABASE_URL = "..."` first. The suite refuses to run against a database whose name does not contain `test`, because it deletes every row.

## Configuration

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://...`; Alembic converts it for its own driver |
| `SECRET_KEY` | yes | signs the JWTs |
| `REDIS_URL` | no | caching is off when unset |
| `CORS_ORIGINS` | no | JSON list, default `["http://localhost:3000"]` |
| `LOG_LEVEL` | no | default `INFO` |

## API

| Method | Path | Access |
|---|---|---|
| POST | `/auth/register`, `/auth/token` | public |
| GET | `/auth/me` | member |
| GET | `/books` (`skip`, `limit` ≤ 100, `author`), `/books/{id}` | public |
| POST, PATCH, DELETE | `/books`, `/books/{id}` | librarian |
| POST | `/books/{id}/borrow` | member |
| GET | `/loans/me` | member |
| POST | `/loans/{id}/return` | member, own loans only |
| GET | `/loans/overdue` | librarian |
| GET | `/health` | public |

Full request and response schemas are in `/docs`.

## Design decisions

- **Authorization per resource, not just per login.** Returning a loan checks that it is yours, which prevents returning other members' loans by guessing IDs.
- **Response models are whitelists,** so fields like `hashed_password` can never reach a client.
- **Argon2 hashing runs in a thread pool,** so its deliberate slowness does not block other requests.
- **The cache is never a dependency.** Every Redis error falls back to the database. Lists expire after 60 seconds and are invalidated after any book change is committed.
- **One clock.** All loan dates use UTC, so due dates and the overdue report never disagree near midnight.

## Proven by breaking

Each protection was removed to confirm its test fails, then restored:

- Ownership check on returns: another member's return succeeded with `200` instead of `403`.
- Librarian check on adding books: a member could add a book.
- Token signature verification: forged and edited tokens were accepted.

## Known limitations

- Two simultaneous requests for the last copy could both succeed; `SELECT ... FOR UPDATE` would fix it.
- Registering an existing email returns `409`, which reveals that the email is registered.
- The login limit is per IP address, not per account.
