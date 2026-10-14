# Public Library Lending API

[![CI](https://github.com/mohammadrh997/public_library/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammadrh997/public_library/actions/workflows/ci.yml)

A REST API for a public library's lending system. Librarians manage the catalogue; members borrow and return books. Built with FastAPI, async SQLAlchemy, and PostgreSQL, with JWT authentication and role-based access.

## Live demo

The API is deployed at **https://public-library-pwmb.onrender.com**, with interactive documentation at [/docs](https://public-library-pwmb.onrender.com/docs).

It runs on Render's free tier, with a free Neon PostgreSQL database, both in Frankfurt. After 15 minutes without traffic the service stops, and the next request starts it again. Measured: the first request after an idle period took about 44 seconds; the next took about 0.3 seconds. If the first request seems to hang, give it a minute.

## Features

- Member registration and login with JWT access tokens
- Two roles: members borrow and return books, librarians also manage the catalogue
- Book catalogue with pagination and author filtering
- Borrowing rules enforced server-side: no borrowing a book with no free copies, and no borrowing a second copy of a book you already have
- Members can only return their own loans
- Overdue loan report for librarians
- Borrow events logged in the background without delaying the response
- Reversible database migrations with Alembic
- Book list cached in Redis, with `ETag` and `304 Not Modified` support on book details
- Login rate limited to 5 attempts per minute per client
- Health check endpoint for hosting platforms

## Tech stack

| Area | Choice |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 (async, `asyncpg` driver) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Authentication | JWT via PyJWT, passwords hashed with Argon2 via `pwdlib` |
| Configuration | `pydantic-settings` reading from `.env` |
| Testing | pytest, pytest-asyncio, httpx2 |
| Code quality | Ruff, mypy, pre-commit |
| Caching | Redis via `redis.asyncio` |
| Rate limiting | slowapi |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions: lint, format check, type check, migration checks, tests |
| Deployment | Render (Docker), Neon PostgreSQL, continuous deployment from `main` gated by CI |

## Project structure

```
app/
    main.py            app creation, routers, exception handlers, CORS, lifespan
    config.py          settings loaded from the environment
    database.py        engine, session factory, declarative base
    models.py          SQLAlchemy models: Member, Book, Loan
    schemas.py         Pydantic request and response models
    security.py        password hashing and JWT creation/verification
    dependencies.py    database session, current member, librarian guard, pagination
    exceptions.py      custom exceptions and their handlers
    cache.py           Redis client, cache helpers, invalidation
    rate_limit.py      the shared slowapi limiter
    routers/
        auth.py        register, login, current member
        books.py       catalogue management and borrowing
        loans.py       a member's loans, returns, overdue report
        health.py      health check for the hosting platform
.github/workflows/     CI pipeline
alembic/               database migrations
tests/                 unit and API tests
Dockerfile             container image definition
compose.yaml           local stack: PostgreSQL, Redis, and the API
start.sh               container entry point: runs migrations, then starts the server
```

## Quick start with Docker Compose

The fastest way to run everything. You only need Docker; PostgreSQL and Python do not have to be installed.

```bash
git clone https://github.com/mohammadrh997/public_library.git
cd public_library
cp .env.example .env
```

Set `SECRET_KEY` in `.env` (see step 3 below for how to generate one). Compose refuses to start without it. Then:

```bash
docker compose up --build
```

This starts three containers: PostgreSQL 18, Redis, and the API. The API waits until the database reports healthy, runs the migrations, and serves at `http://localhost:8000`, with documentation at `http://localhost:8000/docs`.

Promote a registered member to librarian:

```bash
docker compose exec db psql -U library -d library -c "UPDATE members SET is_librarian = true WHERE email = 'librarian@example.com';"
```

Inside the stack the API reaches the database at `db:5432`. The database is also published on your machine at `localhost:5433` (user and password `library`), so it does not clash with a PostgreSQL already installed on port 5432.

**Running the tests against the Compose database.** Create the test database once:

```bash
docker compose exec db psql -U library -d library -c "CREATE DATABASE library_test;"
```

Then run the suite through the published port. On Linux or macOS:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://library:library@localhost:5433/library_test pytest -q
```

In Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://library:library@localhost:5433/library_test"
pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

**Stopping.** `docker compose down` stops and removes the containers but keeps all data, including `library_test`, in the `pgdata` volume. `docker compose down -v` also deletes the volume: every member, book, and loan, and the test database, which must then be created again.

After changing code, `requirements.txt`, or the Dockerfile, use `docker compose up --build`; without `--build`, Compose reuses the previous image.

## Getting started without Docker

### Prerequisites

- Python 3.10 or newer
- PostgreSQL 12 or newer

### 1. Clone and install

```bash
git clone https://github.com/mohammadrh997/public_library.git
cd public_library
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Create the database

In `psql`, connected as a PostgreSQL superuser:

```sql
CREATE USER library_app WITH PASSWORD 'choose-a-password';
CREATE DATABASE library OWNER library_app;
```

Making the new user the database owner gives it permission to create tables, which the migrations need.

### 3. Configure the environment

Copy the example file and fill it in:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://USER:PASSWORD@localhost:5432/DATABASE_NAME` |
| `SECRET_KEY` | yes | Signs the JWT tokens. Keep it secret. |
| `ALGORITHM` | no | JWT signing algorithm, default `HS256` |
| `ACCESS_TOKEN_EXP_MINUTES` | no | Token lifetime in minutes, default `30` |
| `REDIS_URL` | no | Redis connection, for example `redis://localhost:6379/0`. Caching is off when unset |
| `CORS_ORIGINS` | no | Allowed origins as a JSON list, default `["http://localhost:3000"]` |
| `LOG_LEVEL` | no | Logging level, default `INFO` |
| `TEST_DATABASE_URL` | for tests | Like `DATABASE_URL`, but for a separate database whose name contains `test` |

Generate a strong secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The application uses the async `asyncpg` driver, while Alembic runs migrations synchronously. You only set `DATABASE_URL` once: `alembic/env.py` switches the driver automatically.

### 4. Run the migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
fastapi dev app/main.py
```

The API is now at `http://127.0.0.1:8000`, with interactive documentation at `http://127.0.0.1:8000/docs`.

### 6. Create a librarian

Registration always creates an ordinary member, so that nobody can grant themselves librarian access through the API. Register an account normally, then promote it in `psql`:

```sql
UPDATE members SET is_librarian = true WHERE email = 'librarian@example.com';
```

### 7. Run the tests

Create a separate test database owned by the same user:

```sql
CREATE DATABASE library_test OWNER library_app;
```

Its name must contain `test`, or the suite refuses to run, because the tests delete every row after each test. Set `TEST_DATABASE_URL` in `.env`.

The cache and rate-limit tests also need Redis. Start it with `docker compose up -d redis`, which publishes it on `localhost:6379`. Then run:

```bash
pytest -q
```

### 8. Run with Docker

Build the image:

```bash
docker build -t library-api .
```

Run it against PostgreSQL on your machine, replacing `USER`, `PASSWORD`, and the database name:

```bash
docker run --rm -p 8000:8000 --env-file .env -e DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@host.docker.internal/library library-api
```

Inside a container, `localhost` means the container itself, so the database address is overridden with `host.docker.internal`, which reaches your machine on Docker Desktop. Migrations run automatically when the container starts, and `.env` is never copied into the image.

## API reference

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/auth/register` | public | Create a member account |
| POST | `/auth/token` | public | Log in and receive an access token |
| GET | `/auth/me` | member | The current member's details |
| GET | `/books` | public | List books. Query parameters: `skip`, `limit` (max 100), `author` (author name) |
| GET | `/books/{book_id}` | public | A single book |
| POST | `/books` | librarian | Add a book |
| PATCH | `/books/{book_id}` | librarian | Update a book; only the fields sent are changed |
| DELETE | `/books/{book_id}` | librarian | Delete a book. Refused if the book has loan records |
| POST | `/books/{book_id}/borrow` | member | Borrow a book for 14 days |
| GET | `/loans/me` | member | The current member's loans, with book details |
| POST | `/loans/{loan_id}/return` | member | Return one of your own loans |
| GET | `/loans/overdue` | librarian | Unreturned loans past their due date, with book and member details |
| GET | `/health` | public | `200` when the database is reachable, `503` when it is not |

Protected endpoints expect the token in an `Authorization: Bearer <token>` header. In `/docs`, the **Authorize** button handles this for you.

### Error responses

| Status | Meaning |
|---|---|
| 401 | Missing, invalid, or expired token, or wrong login credentials |
| 403 | Authenticated but not permitted, such as a member acting as a librarian, or returning someone else's loan |
| 404 | The requested book or loan does not exist |
| 409 | Conflicts with current state: duplicate email or ISBN, borrowing a book with no free copies or one you already have, returning a loan twice, deleting a book with loan history |
| 422 | Invalid input |
| 429 | Too many login attempts; wait a minute and try again |
| 500 | Unexpected server error. Details are logged server-side and never returned to the client |

## Example

```bash
# Register
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "reader@example.com", "name": "Reader", "password": "a-long-passphrase"}'

# Log in (form data, not JSON, per the OAuth2 standard)
curl -X POST http://127.0.0.1:8000/auth/token \
  -d "username=reader@example.com&password=a-long-passphrase"

# Borrow a book, using the access_token from the login response
curl -X POST http://127.0.0.1:8000/books/1/borrow \
  -H "Authorization: Bearer <access_token>"
```

## Design decisions

**Authorization is checked per resource, not only per login.** Being logged in proves who you are, not what you may touch. Returning a loan checks that it belongs to you, which prevents one member returning another's books by guessing IDs (an IDOR vulnerability). The existence check runs before the ownership check, so the API does not reveal which loan IDs exist.

**Response models are whitelists.** Every endpoint declares a response model, so fields like `hashed_password` can never reach a client, even by accident. Registration likewise ignores any `is_librarian` value a client sends.

**Password hashing does not block the server.** Argon2 is deliberately slow and memory-hard, which is what makes stolen hashes expensive to crack. Because that work would otherwise stall the async event loop and delay every other request, hashing and verification run in a thread pool.

**Related data is eagerly loaded.** Endpoints that return nested objects, such as a loan with its book, load those relationships in the same query using `selectinload`. This avoids the N+1 query problem, and async SQLAlchemy would raise an error on a lazy load anyway.

**Migrations are reversible.** The declarative base uses a constraint naming convention, so every constraint has a predictable name written into the migration file. Without it, PostgreSQL names constraints itself, and downgrades that drop a constraint fail because the migration does not know the name.

**The cache is an optimisation, never a dependency.** Every Redis call is wrapped so that a Redis failure falls back to the database with a logged warning, instead of an error for the user. Cached lists expire after 60 seconds and are invalidated whenever a book is added, changed, or deleted, after the database commit succeeds.

**Login is rate limited per client address.** Five attempts per minute, counted in Redis so every process shares one limit, with an in-memory fallback so a Redis outage never blocks login.

**Login does not reveal which emails are registered.** A wrong password and an unknown email return the same `401` with the same body, and they take the same time: when the email is unknown, the password is still checked against a dummy Argon2 hash, so the response is not measurably faster.

**Nothing untested reaches production.** `main` is protected: every change arrives through a pull request, which can only merge once CI passes. Render deploys automatically from `main`, and the container runs any pending migrations before the server starts.

**Logging borrows does not slow borrowing.** Each successful borrow is logged as a background task, which runs after the response has been sent. It goes to standard output rather than a file, so it survives in the platform's logs when a container is replaced.

## Known limitations and next steps

- **Concurrent borrowing of the last copy.** Borrowing checks the number of free copies and then creates the loan. Two requests arriving at the same moment could both pass the check. Locking the relevant rows with `SELECT ... FOR UPDATE` inside the transaction would close this.
- **Registration reveals whether an email exists.** Registering an existing email returns `409`. Closing this would need a registration flow that always responds the same way and confirms by email.
- **Free-tier cold starts.** The live demo sleeps after 15 minutes of inactivity, so the first request afterwards is slow, as described under Live demo.
- **The login limit is per address, not per account.** Clients behind one address share a limit, and a client that can vary its address can get around it. Counting failed attempts per account as well would close this.
