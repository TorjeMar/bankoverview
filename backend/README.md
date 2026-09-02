# personal-finance-backend

FastAPI backend for a personal finance dashboard using Open Banking (via
[Enable Banking](https://enablebanking.com/)).

## Features

- FastAPI backend, organized by feature (`auth`, `connections`, `accounts`)
- Enable Banking OAuth flow with RS256 JWT authentication
- HTTP-only session cookies for the application's own auth
- Postgres persistence for bank connections, managed with Alembic migrations
- In-memory storage for short-lived state (app sessions, pending authorizations)
- Environment-based configuration using Pydantic Settings
- Auto-generated dev dashboard at `/dev` for exercising every endpoint

---

## Project Structure

```text
backend
├── src/app
│   ├── api
│   │   └── router.py           # mounts feature routers under /api/v1
│   ├── core
│   │   ├── config.py            # Settings (env vars)
│   │   └── exceptions.py
│   ├── database.py               # SQLAlchemy engine/session, Base, in-memory stores
│   ├── features
│   │   ├── auth                  # login, session cookie, get_current_user
│   │   ├── connections           # bank authorization start/callback, BankConnection
│   │   └── accounts               # accounts, balances, transactions
│   ├── integrations
│   │   └── enable_banking         # Enable Banking API client, schemas, exceptions
│   ├── static
│   │   └── index.html             # dev dashboard, reads /openapi.json
│   └── main.py
├── migrations                     # Alembic environment + versions
├── alembic.ini
├── tests
├── pyproject.toml
└── uv.lock
```

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for the local Postgres container)
- An Enable Banking application + private key

---

## Installation

From the repo root:

```bash
cd backend
uv sync
```

---

## Configuration

Create `backend/.env`:

```env
KEY_PATH=../secrets/private_key.pem

APPLICATION_ID=<application-id>

API_ORIGIN=https://api.enablebanking.com

ASPSP_NAME=DNB
ASPSP_COUNTRY=NO

CALLBACK_URL=http://localhost:8000/api/v1/connections/callback

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/openbanking
```

Place your private key at the path referenced by `KEY_PATH`, e.g.

```
secrets/private_key.pem
```

---

## Database

Start Postgres (from the repo root, where `docker-compose.yml` lives):

```bash
docker compose up -d postgres
```

Apply migrations:

```bash
cd backend
uv run alembic upgrade head
```

---

## Running

```bash
cd backend
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`, mounted under `/api/v1`.

- Interactive docs: `http://localhost:8000/docs`
- Dev dashboard (click-through explorer built from `/openapi.json`): `http://localhost:8000/dev`

---

## Authentication Flow

### 1. Login

```
POST /api/v1/login
```

Creates an application session and stores an HTTP-only cookie.

---

### 2. Start bank authorization

```
POST /api/v1/connections/start
```

Requires authentication.

Creates a pending authorization and returns the Enable Banking authorization URL.

---

### 3. Authenticate with the bank

The user authenticates with the selected bank through Enable Banking.

---

### 4. Callback

```
GET /api/v1/connections/callback
```

Enable Banking redirects the user back with `state` and `code`. The application:

- validates the authorization state
- exchanges the authorization code
- persists the bank connection to Postgres

---

### 5. Retrieve accounts, balances and transactions

Once a bank connection exists, the accounts endpoints use it to talk to
Enable Banking directly (accounts and their transactions are not persisted —
only the connection is).

---

## Current Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/login` | Log in and start a session |
| POST | `/api/v1/connections/start` | Start bank authorization |
| GET | `/api/v1/connections/callback` | Handle bank authorization callback |
| GET | `/api/v1/accounts` | List accounts |
| GET | `/api/v1/accounts/{account_id}` | Get account details |
| GET | `/api/v1/accounts/{account_id}/balances` | Get account balances |
| GET | `/api/v1/accounts/{account_id}/transactions` | List account transactions |
| GET | `/api/v1/accounts/{account_id}/transactions/{transaction_id}` | Get a single transaction |

---

## Current Limitations

- App sessions and pending bank authorizations are still in-memory and are
  lost on restart (bank connections are the only thing persisted to Postgres).
- Only the current user's active bank connection is used — no support for
  multiple simultaneous connections yet.
- Accounts, balances and transactions are fetched live from Enable Banking
  on every request rather than cached/persisted locally.

---

## Future Improvements

- Persist app sessions and pending authorizations (or move them to Redis)
- Support multiple bank connections per user
- Refresh consent before it expires
- Cache/persist accounts and transactions
- Frontend
- Docker deployment for the API itself
