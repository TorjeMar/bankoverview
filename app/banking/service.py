from datetime import datetime, timezone

from app.banking.types import BankConnection, BankConnectionResponse
from app.enable_banking.types import EnableBankingSession
from app.storage.memory import bank_connections


def save_bank_connection(
    user_id: str,
    session: EnableBankingSession,
) -> BankConnection:
    valid_until = (
        session.access.valid_until
        if session.access is not None
        else None
    )

    connection = BankConnection(
        user_id=user_id,
        enable_banking_session_id=session.session_id,
        status="authorized",
        created_at=datetime.now(timezone.utc),
        valid_until=valid_until,
        aspsp=session.aspsp,
        account_metadata=session.accounts,
    )

    bank_connections.setdefault(user_id, []).append(connection)
    return connection


def to_bank_connection_response(
    connection: BankConnection,
) -> BankConnectionResponse:
    return BankConnectionResponse(
        status=connection.status,
        created_at=connection.created_at,
        valid_until=connection.valid_until,
        aspsp=connection.aspsp,
        account_count=len(connection.account_metadata),
    )
