from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.features.accounts.models import BankAccountModel
from app.features.auth.models import UserModel
from app.features.connections.models import BankConnectionModel
from app.features.connections.service import save_bank_connection
from app.integrations.enable_banking.schemas import (
    AccountId,
    AccountServicer,
    CreatedEnableBankingSession,
    EnableBankingAccess,
    EnableBankingAccount,
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


@pytest.mark.asyncio
async def test_save_bank_connection_persists_connection_and_accounts(
    db: AsyncSession, test_user: UserModel
) -> None:
    fake_session = CreatedEnableBankingSession(
        session_id="fake-session-id",
        access=EnableBankingAccess(valid_until=datetime.now(UTC) + timedelta(days=10)),
        accounts=[
            EnableBankingAccount(
                uid="fake-account-uid",
                account_id=AccountId(iban="NO1234567890123"),
                name="Test Account",
                currency="NOK",
                cash_account_type="CACC",
                account_servicer=AccountServicer(bic_fi="TESTNOKK"),
            )
        ],
    )

    connection = await save_bank_connection(
        db, user_id=str(test_user.user_id), session=fake_session
    )

    # re-fetch to prove it's actually in the database, not just the object
    # we already have in memory
    stored_connection = await db.get(BankConnectionModel, connection.connection_id)
    assert stored_connection is not None
    assert stored_connection.status == "active"
    assert stored_connection.user_id == test_user.user_id
    assert stored_connection.enable_banking_session_id == "fake-session-id"

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
