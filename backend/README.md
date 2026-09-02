# personal-finance-backend

FastAPI backend for a personal finance dashboard using Open Banking (via
[Enable Banking](https://enablebanking.com/)).

## Features

- FastAPI backend, organized by feature (`auth`, `connections`, `accounts`)
- Enable Banking OAuth flow with RS256 JWT authentication
- HTTP-only session cookies for the application's own auth
- Postgres persistence for users, banks, bank connections, and bank accounts
  (`users` / `banks` / `bank_connections` / `bank_accounts`), managed with
  Alembic migrations
- In-memory storage for short-lived state (app sessions, pending authorizations)
- Environment-based configuration using Pydantic Settings
- Auto-generated dev dashboard at `/dev` for exercising every endpoint

---

## Project Structure

```text
backend
├── src/app
│   ├── api
│   │   └── router.py              # mounts feature routers under /api/v1
│   ├── core
│   │   └── config.py              # Settings (env vars)
│   ├── database.py                # SQLAlchemy engine/session, Base, in-memory stores
│   ├── features
│   │   ├── auth                   # login, session cookie, get_current_user, UserModel
│   │   ├── connections            # bank auth start/callback, BankConnectionModel, BankModel
│   │   └── accounts                # accounts/balances/transactions, BankAccountModel, TransactionModel
│   ├── integrations
│   │   └── enable_banking         # Enable Banking API client, schemas, error translation
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
- resolves (or creates) the `Bank` row and persists the `BankConnection`
- persists one `BankAccount` row per account returned in the session
  (IBAN, name, currency, cash account type, servicer BIC — all available
  from the session-creation response, no extra API call needed)

---

### 5. Retrieve accounts, balances and transactions

`GET /accounts/{id}`, `/balances`, and `/transactions` all check the
requested `account_id` against the persisted `BankAccount` rows before
doing anything else, so one user can't query another user's account by
guessing an ID. `GET /accounts` (the list) and the actual account/balance/
transaction data itself are still fetched live from Enable Banking on every
request — only the connection and account *identities* are persisted so
far, not balances or transaction history (see "Future Improvements").

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
| GET | `/api/v1/accounts/{account_id}/transactions/{transaction_id}` | Get a single transaction — **currently broken**, see Limitations |

---

## Current Limitations

- App sessions and pending bank authorizations are still in-memory and are
  lost on restart. Users, banks, bank connections, and bank accounts persist
  to Postgres.
- `/login` derives a user's UUID deterministically from whatever string it's
  given (`uuid5` against a fixed namespace) rather than real authentication —
  there's no password, no registration, and no way to prove identity yet.
- Only the current user's active bank connection is used — no support for
  multiple simultaneous connections yet.
- Balances and transactions are fetched live from Enable Banking on every
  request rather than cached/persisted locally. Enable Banking/DNB also rate
  limits unattended account access to a few calls per day per connection, so
  repeated live calls can exhaust that quota.
- There's no endpoint to fetch a single transaction by ID that actually
  works — DNB doesn't implement one at the ASPSP level (confirmed via a
  `501 Not Implemented` relayed through Enable Banking), so this needs to be
  solved by persisting transactions locally and looking them up there
  instead (see `notes/plans/transaction-sync.md`, not committed).

---

## Future Improvements

- Persist app sessions and pending authorizations (or move them to Redis)
- Real authentication to replace the deterministic-UUID `/login` stand-in
- Support multiple bank connections per user
- Refresh consent before it expires
- Sync and persist transactions locally (full backfill + periodic re-sync),
  which also fixes single-transaction lookup and reduces live API calls
  against Enable Banking's rate limit
- Frontend
- Docker deployment for the API itself
