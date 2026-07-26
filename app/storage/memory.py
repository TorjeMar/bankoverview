from app.auth.types import PendingAuthorization
from app.banking.types import BankConnection

app_sessions: dict[str, dict[str, str]] = {}
pending_authorizations: dict[str, PendingAuthorization] = {}
bank_connections: dict[str, list[BankConnection]] = {}
