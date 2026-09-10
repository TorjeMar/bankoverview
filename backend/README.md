# personal-finance-backend

FastAPI backend for a personal finance dashboard using Open Banking (via
[Enable Banking](https://enablebanking.com/)).

## Features

- FastAPI backend, organized by feature (`auth`, `connections`, `accounts`,
  `overview`)
- Google OAuth login (via Authlib) with revocable, DB-backed sessions (JWT
  `sid` claim + `sessions` table) and double-submit CSRF protection on every
  state-changing route
- Enable Banking OAuth flow with RS256 JWT authentication for bank access
  (separate from the app's own Google login), with a bank picker
  (`GET /connections/banks`) so a user can connect more than one bank —
  reconnecting the same bank supersedes only that bank's prior connection,
  other banks stay active
- Disconnect (revoke) and reauth for bank connections, including revoking
  consent on Enable Banking's side (`DELETE /sessions/{id}`), not just locally
- Postgres persistence for users, banks, bank connections, bank accounts, and
  transactions (`users` / `banks` / `bank_connections` / `bank_accounts` /
  `transactions`), managed with Alembic migrations
- Quota-conscious dashboard data: `GET /overview` is a pure DB read (cached
  balances + persisted transactions, aggregated across every active
  connection); `POST /sync` is the only user-triggered call that actually
  hits Enable Banking, since account access is rate-limited to a few calls a
  day per connection
- Booked/available balance in `/overview` reflects still-pending transactions
  live (subtracts pending debits, adds pending credits) rather than lagging
  until the bank books them
- Per-account custom display name (`PATCH /accounts/{id}`) and manual drag-
  and-drop ordering (`PUT /accounts/order`), both persisted and carried
  forward across a bank reconnect by matching `iban` — Enable Banking's own
  `account_id` isn't stable across a fresh authorization, `iban` is
- Internal transfers between a user's own accounts (bank-labeled
  "Kontoregulering") and ISO 4217 "XXX" (no-currency) transactions are
  excluded from the in/out/net currency totals; a still-pending "XXX"
  transaction (no currency assigned yet) displays as the account's own
  currency rather than the literal code, and is still included in that
  account's live balance adjustment
- Dashboard charts (overview balance history, per-account activity) support
  hover — a tooltip shows the exact balance and date at any point
- In-memory storage only for short-lived state (pending bank authorizations
  mid-handshake)
- Environment-based configuration using Pydantic Settings
- End-user dashboard served at `/app`, with `Cache-Control: no-cache` on
  every asset so a redeploy is never masked by a stale browser cache

---

## Project Structure

```text
backend
├── src/app
│   ├── api
│   │   └── router.py              # mounts feature routers under /api/v1
│   ├── core
│   │   ├── config.py              # Settings (env vars)
│   │   └── csrf.py                # double-submit CSRF token generation
│   ├── database.py                # SQLAlchemy engine/session, Base, in-memory stores
│   ├── features
│   │   ├── auth                   # Google OAuth login, sessions table, CSRF, get_current_user, UserModel
│   │   ├── connections            # bank auth start/callback/revoke, BankConnectionModel, BankModel
│   │   ├── accounts               # accounts/balances/transactions (synced), rename, reorder
│   │   └── overview                # GET /overview (DB read) + POST /sync (live refresh)
│   ├── integrations
│   │   └── enable_banking         # Enable Banking API client, schemas, error translation
│   ├── static
│   │   └── dashboard              # end-user dashboard, served at /app
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
- Dashboard: `http://localhost:8000/app`

---

## Authentication Flow

### 1. Login

```
GET /api/v1/login
```

Full-page redirect into Google's OAuth consent screen (not a plain API call —
open it in a browser, or use the dashboard's login button).
`GET /api/v1/login/callback` handles Google's redirect back: it looks up or
creates a `User` by Google's `sub` claim, mints a JWT (`user_id` + `sid` +
7-day `exp`, HS256, signed with `SESSION_SECRET`) backed by a `sessions` row
so it can be revoked on logout, sets it as an HTTP-only `session_token`
cookie plus a readable `csrf_token` cookie, and redirects to `/app/`.

---

All state-changing requests (`POST`/`PUT`/`PATCH`/`DELETE`) also require an
`X-CSRF-Token` header matching the readable `csrf_token` cookie — a
double-submit check (`HMAC-SHA256(SESSION_SECRET, session_id)`), verified
with a constant-time comparison.

---

### 2. Pick a bank and start authorization

```
GET  /api/v1/connections/banks
POST /api/v1/connections/start
```

Requires authentication. `GET /connections/banks` lists the ASPSPs Enable
Banking offers for the configured country. `POST /connections/start` takes
an optional `{bank_name, bank_country}` body (falls back to the
`ASPSP_NAME`/`ASPSP_COUNTRY` env defaults if omitted), creates a pending
authorization, and returns the Enable Banking authorization URL.

---

### 3. Authenticate with the bank

The user authenticates with the selected bank through Enable Banking.

---

### 4. Callback

```
GET /api/v1/connections/callback
```

Reached only via Enable Banking's own browser redirect (never called via
`fetch`), so every outcome — success or failure — redirects the browser to
`/app/?connection=<status>` rather than returning JSON. It responds
immediately — it doesn't wait for the transaction backfill (see below), so
the redirect isn't stuck behind however long that takes. On success it:

- validates the authorization state
- exchanges the authorization code
- resolves (or creates) the `Bank` row and persists the `BankConnection`
  with `status="active"` immediately — the connection and its accounts are
  usable right away, before any transaction history has synced
- marks the user's previous active connection **to that same bank** (if any)
  `"superseded"` — connections to other banks are left active, so a user can
  hold several simultaneous bank connections
- upserts one `BankAccount` row per account returned in the session, keyed on
  `account_id` (IBAN, name, currency, cash account type, servicer BIC — all
  available from the session-creation response, no extra API call needed),
  carrying forward any existing `display_name`/`sort_order` matched by `iban`
- queues the transaction/balance backfill as a background task
  (`backfill_bank_connection`) and returns — 730 days of transaction history
  and an initial balance snapshot per account (Enable Banking's `date_from`
  has no documented default when omitted — observed silently defaulting to
  ~30 days on at least one ASPSP), each account synced concurrently rather
  than one at a time. Each account's own `sync_status`/`last_synced_at`
  (null until its backfill finishes, `"ok"`/`"error"` after) is how
  `GET /overview` reports per-account progress — a fast account (few
  transactions) shows up before a slow one finishes, rather than the whole
  dashboard waiting on the slowest account. The dashboard polls while any
  account is still unsynced.

---

### 5. Disconnect

```
DELETE /api/v1/connections/{connection_id}
```

Requires authentication and ownership of the connection. Revokes consent on
Enable Banking's side (`DELETE /sessions/{session_id}`) and marks the local
`BankConnection` `"revoked"` — a soft delete, so `bank_accounts`/
`transactions` stay in place as history and simply stop being reachable
through an active connection.

---

### 6. Dashboard data: overview and sync

```
GET  /api/v1/overview?days=30
POST /api/v1/sync
```

`GET /overview` is a pure Postgres read — cached balances (adjusted live for
any still-pending transactions) and persisted transactions, aggregated
across every one of the user's active connections. It never calls Enable
Banking, so it's safe to call on every dashboard load regardless of rate
limits. `POST /sync` is the only user-triggered action that actually hits
Enable Banking: it refreshes balances and the last 7 days of transactions
for every account on every active connection, and returns a summary
(`accounts_synced`, `transactions_synced`, `failed`).

---

### 7. Account rename and reorder

```
PATCH /api/v1/accounts/{account_id}
PUT   /api/v1/accounts/order
```

Both require authentication and ownership, checked across all of the user's
connections (not just one). `PATCH` sets a `display_name` override (empty
string clears it, reverting to the bank's own account name) that survives
reconnect syncs. `PUT /order` takes the full desired list of `account_id`s
and persists each one's position as `sort_order`, also reconnect-safe.

---

## Current Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/login` | Start Google login (browser redirect) |
| GET | `/api/v1/login/callback` | Google OAuth callback — creates the session, redirects to `/app/` |
| GET | `/api/v1/me` | Get the current user |
| POST | `/api/v1/logout` | Revoke the current session |
| GET | `/api/v1/connections/banks` | List connectable banks |
| POST | `/api/v1/connections/start` | Start bank authorization |
| GET | `/api/v1/connections/callback` | Handle bank authorization callback (redirects browser to `/app/`) |
| DELETE | `/api/v1/connections/{connection_id}` | Disconnect a bank connection |
| GET | `/api/v1/overview` | Dashboard data — DB-only read, aggregated across all active connections |
| POST | `/api/v1/sync` | Refresh balances and recent transactions from every active connection |
| GET | `/api/v1/accounts` | List accounts (live, single-connection legacy) |
| GET | `/api/v1/accounts/{account_id}` | Get account details (live) |
| GET | `/api/v1/accounts/{account_id}/balances` | Get account balances (live) |
| GET | `/api/v1/accounts/{account_id}/transactions` | Sync (last 7 days) then list account transactions from Postgres |
| PATCH | `/api/v1/accounts/{account_id}` | Set a custom display name |
| PUT | `/api/v1/accounts/order` | Reorder accounts |

---

## Current Limitations

- Only pending bank authorizations (mid-handshake, short-lived) are still
  in-memory. Users, banks, bank connections, bank accounts, and transactions
  all persist to Postgres.
- The legacy `GET /accounts/{id}`, `/balances`, `/transactions` still fetch
  live from Enable Banking on every request rather than the cached/persisted
  data `/overview` uses — kept for now since nothing in the dashboard calls
  them, but they'd need the same caching treatment before real use. They are
  ownership-checked across all of a user's connections, unlike the bare
  `GET /accounts` (list) endpoint, which is still scoped to a single
  connection (the newest active one) rather than the multi-bank model.
- Internal-transfer detection (`GET /overview`'s currency totals) relies on
  the bank's own "Kontoregulering" label — a transfer to an account we don't
  track (e.g. a credit card or another bank entirely) has no such label and
  still counts as real spending, since there's no way to know it's "yours"
  without that account also being connected here.
- No support for account/connection ownership beyond "the current session's
  user" — no sharing, no admin views.
- No test database isolation — the test suite runs against the real dev
  Postgres instance.

---

## Future Improvements

- Persist pending bank authorizations (or move them to Redis) instead of
  in-memory
- Proactively refresh consent before it expires, rather than relying on the
  user to notice and reconnect
- Bring the legacy live `/accounts` endpoints in line with `/overview`'s
  multi-connection, DB-cached model (or remove them)
- Dedicated test database instead of running the suite against dev Postgres
- Docker deployment for the API itself
