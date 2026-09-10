from datetime import UTC, date, datetime, timedelta

import requests
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.accounts import repository as accounts_repository
from app.features.accounts.service import sync_account_balance, sync_transactions_for_account
from app.features.connections import repository
from app.features.connections.models import BankConnectionModel
from app.features.connections.schemas import BankConnectionResponse
from app.integrations.enable_banking.client import delete_enable_banking_session
from app.integrations.enable_banking.exceptions import to_enable_banking_http_exception
from app.integrations.enable_banking.schemas import CreatedEnableBankingSession

# Enable Banking's `date_from` docs don't state a default or a cap when
# omitted — DNB was observed defaulting to ~30 days. Ask further back
# explicitly; the ASPSP still caps it to whatever it actually allows.
BACKFILL_HISTORY = timedelta(days=730)


async def save_bank_connection(
    db: AsyncSession,
    user_id: str,
    session: CreatedEnableBankingSession,
    bank_name: str | None = None,
    bank_country: str | None = None,
) -> BankConnectionModel:
    bank = await repository.get_or_create_bank(
        db,
        name=bank_name or settings.aspsp_name,
        country_code=bank_country or settings.aspsp_country,
    )

    connection = BankConnectionModel(
        user_id=user_id,
        bank_id=bank.bank_id,
        enable_banking_session_id=session.session_id,
        status="active",
        created_at=datetime.now(UTC),
        valid_until=(
            session.access.valid_until
            if session.access is not None
            else None
        ),
    )
    connection = await repository.save(db, connection)

    await repository.supersede_active_connections_for_bank(
        db, user_id, bank.bank_id, connection.connection_id
    )

    accounts = [
        {
            "account_id": account.uid,
            "connection_id": connection.connection_id,
            "iban": account.account_id.iban,
            "name": account.name,
            "currency": account.currency,
            "cash_account_type": account.cash_account_type,
            "bic": account.account_servicer.bic_fi if account.account_servicer else None,
        }
        for account in session.accounts
    ]

    await accounts_repository.upsert_bank_accounts(db, accounts)

    for account in session.accounts:
        await sync_transactions_for_account(
            db, account.uid, since=date.today() - BACKFILL_HISTORY
        )
        try:
            await sync_account_balance(db, account.uid)
        except (requests.RequestException, ValidationError):
            await accounts_repository.update_account_balance(
                db, account.uid, sync_status="error"
            )

    return connection

async def revoke_bank_connection(db: AsyncSession, connection: BankConnectionModel) -> None:
    try:
        delete_enable_banking_session(
            settings=settings, session_id=connection.enable_banking_session_id
        )
    except requests.RequestException as exc:
        raise to_enable_banking_http_exception(exc) from exc

    await repository.revoke_connection(db, connection)

def to_bank_connection_response(
    connection: BankConnectionModel,
    account_count: int,
) -> BankConnectionResponse:
    return BankConnectionResponse(
        connection_id=str(connection.connection_id),
        status=connection.status,
        created_at=connection.created_at,
        valid_until=connection.valid_until,
        account_count=account_count,
    )
