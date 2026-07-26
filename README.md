# Enable Banking API Demo

A FastAPI application demonstrating the Enable Banking authorization flow using OAuth, JWT authentication, and session-based user authentication.

## Features

- FastAPI backend
- Enable Banking OAuth flow
- JWT authentication using RS256
- HTTP-only session cookies
- In-memory user sessions
- In-memory bank connections
- Environment-based configuration using Pydantic Settings

---

## Project Structure

```text
.
├── app
│   ├── auth
│   ├── banking
│   ├── enable_banking
│   ├── storage
│   ├── config.py
│   └── main.py
├── secrets
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── uv.lock
```

---

## Requirements

- Python 3.12+
- uv
- Enable Banking application
- Enable Banking private key

---

## Installation

Clone the repository

```bash
git clone <repository>
cd <repository>
```

Install dependencies

```bash
uv sync
```

---

## Configuration

Create a `.env` file.

Example:

```env
KEY_PATH=secrets/private_key.pem

APPLICATION_ID=<application-id>

API_ORIGIN=https://api.enablebanking.com

ASPSP_NAME=DNB
ASPSP_COUNTRY=NO

CALLBACK_URL=http://localhost:8000/callback
```

Place your private key inside

```
secrets/private_key.pem
```

---

## Running

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at

```
http://localhost:8000
```

Interactive documentation

```
http://localhost:8000/docs
```

---

## Authentication Flow

### 1. Login

```
POST /login
```

Creates an application session and stores an HTTP-only cookie.

---

### 2. Start bank authorization

```
POST /start
```

Requires authentication.

Creates a pending authorization and returns the Enable Banking authorization URL.

---

### 3. Authenticate with the bank

The user authenticates with the selected bank through Enable Banking.

---

### 4. Callback

```
GET /callback
```

Enable Banking redirects the user back with

- state
- code

The application

- validates the authorization state
- exchanges the authorization code
- stores the bank connection

---

### 5. Retrieve accounts

```
GET /accounts
```

Retrieves the latest session from Enable Banking and returns the available accounts.

---

## Current Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/login` | Create application session |
| POST | `/start` | Begin Enable Banking authorization |
| GET | `/callback` | Handle OAuth callback |
| GET | `/accounts` | Retrieve linked accounts |

---

## Current Limitations

This project currently uses in-memory storage.

The following data is lost whenever the application restarts:

- User sessions
- Pending authorizations
- Bank connections

Currently only the first active bank connection is used when retrieving accounts.

---

## Future Improvements

- Database persistence
- Multiple bank connections
- Refresh consent
- Transaction endpoint
- Balance endpoint
- Account details endpoint
- Frontend using Jinja templates
- Docker deployment