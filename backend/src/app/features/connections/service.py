import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import requests
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import async_session_factory
from app.features.accounts import repository as accounts_repository
from app.features.accounts.service import sync_account_balance, sync_transactions_for_account
from app.features.connections import repository
from app.features.connections.models import BankConnectionModel
from app.features.connections.schemas import BankConnectionResponse
from app.integrations.enable_banking.client import delete_enable_banking_session
from app.integrations.enable_banking.exceptions import to_enable_banking_http_exception
from app.integrations.enable_banking.schemas import CreatedEnableBankingSession

logger = logging.getLogger(__name__)

# Enable Banking's `date_from` docs don't state a default or a cap when
# omitted — DNB was observed defaulting to ~30 days. Ask further back
# explicitly; the ASPSP still caps it to whatever it actually allows.
BACKFILL_HISTORY = timedelta(days=730)


async def create_bank_connection(
    db: AsyncSession,
    user_id: str,
    session: CreatedEnableBankingSession,
    bank_name: str | None = None,
    bank_country: str | None = None,
) -> BankConnectionModel:
    # Fast path only — creates the connection/account rows and returns.
    # The transaction/balance backfill is comparatively slow (paginated
    # Enable Banking calls per account) and runs separately in
    # backfill_bank_connection so the OAuth callback isn't stuck waiting
    # on it before it can redirect the browser back.
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

    customizations = await accounts_repository.get_customizations_by_iban(db, user_id)
    accounts = [
        {
            "account_id": account.uid,
            "connection_id": connection.connection_id,
            "iban": account.account_id.iban,
            "name": account.name,
            "currency": account.currency,
            "cash_account_type": account.cash_account_type,
            "bic": account.account_servicer.bic_fi if account.account_servicer else None,
            **customizations.get(account.account_id.iban, {}),
        }
        for account in session.accounts
    ]

    await accounts_repository.upsert_bank_accounts(db, accounts)

    return connection


async def backfill_bank_connection(account_uids: list[str]) -> None:
    # Runs as a FastAPI background task, after the callback has already
    # responded — the connection is already "active" and visible in
    # /overview at this point; each account just carries its own
    # sync_status/last_synced_at (null until this finishes for it), so the
    # dashboard can show accounts as they individually finish instead of
    # gating the whole connection on the slowest one. Each account gets its
    # own session so they can run concurrently: a single AsyncSession isn't
    # safe for concurrent use.
    async def sync_one(account_uid: str) -> None:
        async with async_session_factory() as account_db:
            try:
                await sync_transactions_for_account(
                    account_db, account_uid, since=date.today() - BACKFILL_HISTORY
                )
                await sync_account_balance(account_db, account_uid)
            except Exception:
                # Anything here — an Enable Banking network/validation
                # failure, or a malformed upstream payload tripping the
                # unguarded dict access in to_transaction_model — has to
                # still mark the account "error" and get logged. This runs
                # inside a BackgroundTasks job nothing awaits; a narrower
                # except would let the account sit stuck on a stale/None
                # sync_status with no signal to the dashboard at all.
                logger.exception("Backfill failed for account %s", account_uid)
                await accounts_repository.update_account_balance(
                    account_db, account_uid, sync_status="error"
                )

    results = await asyncio.gather(
        *(sync_one(uid) for uid in account_uids), return_exceptions=True
    )
    for account_uid, result in zip(account_uids, results, strict=True):
        if isinstance(result, BaseException):
            logger.error(
                "sync_one raised past its own try/except for account %s", account_uid,
                exc_info=result,
            )

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
