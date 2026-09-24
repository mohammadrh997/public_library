# Public Library Lending API

A REST API for a public library's lending system. Librarians manage the catalogue; members borrow and return books. Built with FastAPI, async SQLAlchemy, and PostgreSQL, with JWT authentication and role-based access.

## Features

- Member registration and login with JWT access tokens
- Two roles: members borrow and return books, librarians also manage the catalogue
- Book catalogue with pagination and author filtering
- Borrowing rules enforced server-side: no borrowing a book with no free copies, and no borrowing a second copy of a book you already have
- Members can only return their own loans
- Overdue loan report for librarians
- Borrow events logged in the background without delaying the response
- Reversible database migrations with Alembic

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
    routers/
        auth.py        register, login, current member
        books.py       catalogue management and borrowing
        loans.py       a member's loans, returns, overdue report
alembic/               database migrations
```

## Getting started

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

## API reference

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/auth/register` | public | Create a member account |
| POST | `/auth/token` | public | Log in and receive an access token |
| GET | `/auth/me` | member | The current member's details |
| GET | `/books` | public | List books. Query parameters: `skip`, `limit` (max 100), `search` (author name) |
| GET | `/books/{book_id}` | public | A single book |
| POST | `/books` | librarian | Add a book |
| PATCH | `/books/{book_id}` | librarian | Update a book; only the fields sent are changed |
| DELETE | `/books/{book_id}` | librarian | Delete a book. Refused if the book has loan records |
| POST | `/books/{book_id}/borrow` | member | Borrow a book for 14 days |
| GET | `/loans/me` | member | The current member's loans, with book details |
| POST | `/loans/{loan_id}/return` | member | Return one of your own loans |
| GET | `/loans/overdue` | librarian | Unreturned loans past their due date, with book and member details |

Protected endpoints expect the token in an `Authorization: Bearer <token>` header. In `/docs`, the **Authorize** button handles this for you.

### Error responses

| Status | Meaning |
|---|---|
| 401 | Missing, invalid, or expired token, or wrong login credentials |
| 403 | Authenticated but not permitted, such as a member acting as a librarian, or returning someone else's loan |
| 404 | The requested book or loan does not exist |
| 409 | Conflicts with current state: duplicate email or ISBN, returning a loan twice, deleting a book with loan history |
| 422 | Invalid input, or a borrowing rule was broken |
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

**Logging borrows does not slow borrowing.** Each successful borrow is written to a log file as a background task, which runs after the response has been sent.

## Known limitations and next steps

- **Concurrent borrowing of the last copy.** Borrowing checks the number of free copies and then creates the loan. Two requests arriving at the same moment could both pass the check. Locking the relevant rows with `SELECT ... FOR UPDATE` inside the transaction would close this.
- **Date handling uses more than one clock.** Due dates are calculated in UTC, the overdue check uses the server's local date, and `borrowed_at` uses the database's date. These can disagree near midnight on a server not set to UTC.
- **CORS origin is hardcoded.** It should come from configuration, like the database URL, before deployment.
- **The borrow log is a local file.** It is lost on redeployment and would not work across multiple server instances; a real system would use a proper log store or task queue.
- **No automated tests yet.** A pytest suite covering the borrowing rules and the authorization checks is the next addition, followed by containerisation with Docker and a CI pipeline.
- **No rate limiting on login.** Adding it would slow down password guessing.