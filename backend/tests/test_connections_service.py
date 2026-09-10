from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.features.accounts import service as accounts_service
from app.features.accounts.models import BankAccountModel, TransactionModel
from app.features.auth.models import UserModel
from app.features.connections.models import BankConnectionModel
from app.features.connections.service import backfill_bank_connection, create_bank_connection
from app.integrations.enable_banking.schemas import (
    AccountId,
    AccountServicer,
    CreatedEnableBankingSession,
    EnableBankingAccess,
    EnableBankingAccount,
    EnableBankingBalance,
    EnableBankingTransactions,
)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> AsyncGenerator[UserModel]:
    user = UserModel(user_id=uuid4())
    db.add(user)
    await db.commit()
    await db.refresh(user)

    yield user

    await db.delete(user)
    await db.commit()


def _fake_session(uid: str, iban: str = "NO1234567890123") -> CreatedEnableBankingSession:
    return CreatedEnableBankingSession(
        session_id=f"fake-session-{uid}",
        access=EnableBankingAccess(valid_until=datetime.now(UTC) + timedelta(days=10)),
        accounts=[
            EnableBankingAccount(
                uid=uid,
                account_id=AccountId(iban=iban),
                name="Test Account",
                currency="NOK",
                cash_account_type="CACC",
                account_servicer=AccountServicer(bic_fi="TESTNOKK"),
            )
        ],
    )


@pytest.mark.asyncio
async def test_create_bank_connection_persists_connection_and_accounts(
    db: AsyncSession, test_user: UserModel
) -> None:
    # create_bank_connection is the fast, DB-only path — no Enable Banking
    # calls, so unlike backfill_bank_connection this needs no network stubs.
    connection = await create_bank_connection(
        db, user_id=str(test_user.user_id), session=_fake_session("fake-account-uid")
    )

    # re-fetch to prove it's actually in the database, not just the object
    # we already have in memory
    stored_connection = await db.get(BankConnectionModel, connection.connection_id)
    assert stored_connection is not None
    assert stored_connection.status == "active"
    assert stored_connection.user_id == test_user.user_id
    assert stored_connection.enable_banking_session_id == "fake-session-fake-account-uid"

    result = await db.execute(
        select(BankAccountModel).where(
            BankAccountModel.connection_id == connection.connection_id
        )
    )
    accounts = result.scalars().all()

    assert len(accounts) == 1
    assert accounts[0].account_id == "fake-account-uid"
    assert accounts[0].iban == "NO1234567890123"
    assert accounts[0].currency == "NOK"
    assert accounts[0].bic == "TESTNOKK"

    # cleanup: delete what this test created so it can be re-run cleanly.
    # The Bank row (DNB/NO) is deliberately left alone — it's shared
    # reference data, not something this test owns.
    for account in accounts:
        await db.delete(account)
    await db.delete(stored_connection)
    await db.commit()


@pytest.mark.asyncio
async def test_backfill_bank_connection_syncs_accounts_individually(
    db: AsyncSession, test_user: UserModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The connection is already "active" the moment create_bank_connection
    # returns — backfill_bank_connection no longer gates a connection-level
    # status, it just fills in each account's own sync_status/last_synced_at
    # so the dashboard can show accounts progressively instead of waiting
    # for the slowest one.
    monkeypatch.setattr(
        accounts_service,
        "retrieve_account_transactions",
        lambda **kwargs: EnableBankingTransactions(
            transactions=[
                {
                    "transaction_id": "fake-tx-1",
                    "transaction_amount": {"amount": "10.00", "currency": "NOK"},
                    "credit_debit_indicator": "CRDT",
                    "status": "BOOK",
                    "booking_date": "2026-01-01",
                    "remittance_information": ["test"],
                }
            ],
            continuation_key=None,
        ),
    )
    monkeypatch.setattr(
        accounts_service,
        "retrieve_account_balances",
        lambda **kwargs: EnableBankingBalance(balances=[]),
    )

    connection = await create_bank_connection(
        db, user_id=str(test_user.user_id), session=_fake_session("backfill-uid")
    )
    assert connection.status == "active"
    connection_id = connection.connection_id  # read before expiring below
    account_before = await db.get(BankAccountModel, "backfill-uid")
    assert account_before is not None
    assert account_before.sync_status is None  # not yet synced

    await backfill_bank_connection(["backfill-uid"])

    # backfill_bank_connection commits through its own sessions — refresh
    # this test's session's view rather than trusting stale cached state.
    db.expire_all()
    account_after = await db.get(BankAccountModel, "backfill-uid")
    assert account_after is not None
    assert account_after.sync_status == "ok"
    assert account_after.last_synced_at is not None

    result = await db.execute(
        select(TransactionModel).where(TransactionModel.account_id == "backfill-uid")
    )
    transactions = result.scalars().all()
    assert len(transactions) == 1
    assert transactions[0].transaction_id == "fake-tx-1"

    # cleanup — transactions first and committed separately: no ORM
    # relationship is mapped between TransactionModel/BankAccountModel, so a
    # single flush mixing both deletes has no dependency info to order them
    # correctly and can try to delete the account first.
    for transaction in transactions:
        await db.delete(transaction)
    await db.commit()
    await db.delete(account_after)
    await db.delete(await db.get(BankConnectionModel, connection_id))
    await db.commit()


@pytest.mark.asyncio
async def test_create_bank_connection_carries_customizations_across_reconnect_by_iban(
    db: AsyncSession, test_user: UserModel
) -> None:
    # Enable Banking mints a new account uid on every fresh authorization —
    # confirmed live this session, not an assumption — even for the same
    # physical account (same iban). Rename/reorder must survive that.
    first_connection = await create_bank_connection(
        db, user_id=str(test_user.user_id), session=_fake_session("first-uid", "NO9999999999999")
    )
    first_account = await db.get(BankAccountModel, "first-uid")
    assert first_account is not None
    first_account.display_name = "My Custom Name"
    first_account.sort_order = 3
    await db.commit()

    second_connection = await create_bank_connection(
        db, user_id=str(test_user.user_id), session=_fake_session("second-uid", "NO9999999999999")
    )
    second_account = await db.get(BankAccountModel, "second-uid")

    assert second_account is not None
    assert second_account.display_name == "My Custom Name"
    assert second_account.sort_order == 3

    # cleanup
    await db.delete(first_account)
    await db.delete(second_account)
    await db.delete(await db.get(BankConnectionModel, first_connection.connection_id))
    await db.delete(await db.get(BankConnectionModel, second_connection.connection_id))
    await db.commit()
