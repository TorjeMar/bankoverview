# personal-finance-backend

FastAPI backend for a personal finance dashboard using Open Banking (via
[Enable Banking](https://enablebanking.com/)).

## Features

- FastAPI backend, organized by feature (`auth`, `connections`, `accounts`)
- Google OAuth login (via Authlib) with self-contained JWT app sessions —
  survives backend restarts, no server-side session store
- Enable Banking OAuth flow with RS256 JWT authentication for bank access
  (separate from the app's own Google login)
- Disconnect (revoke) and reauth for bank connections, including revoking
  consent on Enable Banking's side (`DELETE /sessions/{id}`), not just locally
- Postgres persistence for users, banks, bank connections, bank accounts, and
  transactions (`users` / `banks` / `bank_connections` / `bank_accounts` /
  `transactions`), managed with Alembic migrations
- Transactions are synced to and read from Postgres rather than fetched live
  on every request
- In-memory storage only for short-lived state (pending bank authorizations
  mid-handshake)
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
│   │   ├── auth                   # Google OAuth login, JWT session cookie, get_current_user, UserModel
│   │   ├── connections            # bank auth start/callback/revoke, BankConnectionModel, BankModel
│   │   └── accounts                # accounts/balances/transactions (synced), BankAccountModel, TransactionModel
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

GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>

SESSION_SECRET=<random 32+ char secret, e.g. `openssl rand -hex 32`>
```

Place your private key at the path referenced by `KEY_PATH`, e.g.

```
secrets/private_key.pem
```

For Google login, create an OAuth 2.0 Client ID (Web application type) in
[Google Cloud Console](https://console.cloud.google.com/apis/credentials),
with `http://localhost:8000/api/v1/login/callback` as an authorized redirect
URI. Use `localhost`, not `127.0.0.1` — Google treats them as different hosts
and will reject the redirect if you browse to the other one.

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
GET /api/v1/login
```

Full-page redirect into Google's OAuth consent screen (not a plain API call —
open it in a browser, or use the dev dashboard's dedicated login button).
`GET /api/v1/login/callback` handles Google's redirect back: it looks up or
creates a `User` by Google's `sub` claim, mints a JWT (`user_id` + 7-day
`exp`, HS256, signed with `SESSION_SECRET`), sets it as an HTTP-only
`session_token` cookie, and redirects to `/dev/`. The JWT is self-contained,
so a session survives a backend restart — nothing server-side backs it.

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
- marks the user's previous active connection (if any) `"superseded"`, so
  exactly one connection is `"active"` per user at a time
- upserts one `BankAccount` row per account returned in the session, keyed on
  `account_id` (IBAN, name, currency, cash account type, servicer BIC — all
  available from the session-creation response, no extra API call needed)

---

### 5. Disconnect

```
DELETE /api/v1/connections/revoke
```

Requires authentication. Revokes consent on Enable Banking's side
(`DELETE /sessions/{session_id}`) and marks the local `BankConnection`
`"revoked"` — a soft delete, so `bank_accounts`/`transactions` stay in place
as history and simply stop being reachable through an active connection.

---

### 6. Retrieve accounts, balances and transactions

`GET /accounts/{id}`, `/balances`, and `/transactions` all check the
requested `account_id` against the persisted `BankAccount` rows before doing
anything else, so one user can't query another user's account by guessing an
ID. `GET /accounts` (the list) and account details/balances are still
fetched live from Enable Banking. Transactions are different: each
`/transactions` request first syncs the last 7 days from Enable Banking into
Postgres (`upsert` keyed on transaction ID), then reads the full history back
from the database — so transaction history is persisted and querying it
doesn't re-hit Enable Banking's rate limit on every page load.

---

## Current Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/login` | Start Google login (browser redirect) |
| GET | `/api/v1/login/callback` | Google OAuth callback — sets the session cookie |
| POST | `/api/v1/connections/start` | Start bank authorization |
| GET | `/api/v1/connections/callback` | Handle bank authorization callback |
| DELETE | `/api/v1/connections/revoke` | Disconnect the active bank connection |
| GET | `/api/v1/accounts` | List accounts |
| GET | `/api/v1/accounts/{account_id}` | Get account details |
| GET | `/api/v1/accounts/{account_id}/balances` | Get account balances |
| GET | `/api/v1/accounts/{account_id}/transactions` | Sync (last 7 days) then list account transactions from Postgres |

---

## Current Limitations

- Only pending bank authorizations (mid-handshake, short-lived) are still
  in-memory. Users, banks, bank connections, bank accounts, and transactions
  all persist to Postgres.
- Only the current user's active bank connection is used — no support for
  multiple simultaneous connections yet (reconnecting supersedes the
  previous one rather than running both).
- Account details and balances are still fetched live from Enable Banking on
  every request rather than cached/persisted locally (transactions already
  are). Enable Banking/DNB rate-limits unattended account access to a few
  calls per day per connection, so repeated live calls can exhaust that
  quota.
- No support for account/connection ownership beyond "the current session's
  user" — no sharing, no admin views.

---

## Future Improvements

- Persist pending bank authorizations (or move them to Redis) instead of
  in-memory
- Support multiple bank connections per user
- Proactively refresh consent before it expires, rather than relying on the
  user to notice and reconnect
- Persist account details/balances locally the same way transactions
  already are, to further reduce live Enable Banking calls
- Frontend
- Docker deployment for the API itself
