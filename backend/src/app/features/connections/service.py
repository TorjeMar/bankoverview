from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.connections import repository
from app.features.connections.models import BankConnectionModel
from app.features.connections.schemas import BankConnectionResponse
from app.integrations.enable_banking.schemas import CreatedEnableBankingSession


async def save_bank_connection(
    db: AsyncSession,
    user_id: str,
    session: CreatedEnableBankingSession,
) -> BankConnectionModel:
    connection = BankConnectionModel(
        user_id=user_id,
        enable_banking_session_id=session.session_id,
        status="active",
        created_at=datetime.now(UTC),
        valid_until=(
            session.access.valid_until
            if session.access is not None
            else None
        ),
        aspsp=session.aspsp,
        account_ids=[
            account.uid
            for account in session.accounts
        ],
    )

    return await repository.save(db, connection)


def to_bank_connection_response(
    connection: BankConnectionModel,
) -> BankConnectionResponse:
    return BankConnectionResponse(
        status=connection.status,
        created_at=connection.created_at,
        valid_until=connection.valid_until,
        aspsp=connection.aspsp,
        account_count=len(connection.account_ids),
    )
