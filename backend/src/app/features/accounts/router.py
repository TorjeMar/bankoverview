from datetime import date, timedelta
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.features.accounts import repository
from app.features.accounts.schemas import (
    AccountBalanceResponse,
    AccountDetailsResponse,
    AccountsResponse,
    AccountTransactionsResponse,
    RenameAccountRequest,
    RenameAccountResponse,
    ReorderAccountsRequest,
)
from app.features.accounts.service import (
    sync_transactions_for_account,
    to_account_balance_response,
    to_account_details_response,
    to_account_transactions_response,
    to_get_accounts_response,
)
from app.features.auth.router import get_current_user, verify_csrf
from app.features.auth.schemas import UserSession
from app.features.connections.models import BankConnectionModel
from app.features.connections.router import get_bank_connection
from app.integrations.enable_banking.client import (
    retrieve_account_balances,
    retrieve_account_details,
    retrieve_enable_banking_session,
)
from app.integrations.enable_banking.exceptions import to_enable_banking_http_exception

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
)


@router.get("", response_model=AccountsResponse, summary="List accounts")
def get_accounts(
    connection: Annotated[
        BankConnectionModel,
        Depends(get_bank_connection),
    ],
) -> AccountsResponse:
    try:
        session = retrieve_enable_banking_session(
            settings=settings,
            session_id=connection.enable_banking_session_id,
        )
    except (requests.RequestException, ValidationError) as exc:
        raise to_enable_banking_http_exception(exc) from exc

    return to_get_accounts_response(session)


@router.get(
    "/{account_id}",
    response_model=AccountDetailsResponse,
    summary="Get account details",
)
async def get_account_details(
    account_id: str,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountDetailsResponse:
    account_link = await repository.get_account_owned_by_user(
        db, current_user.user_id, account_id
    )
    if account_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    try:
        account = retrieve_account_details(
            settings=settings,
            account_id=account_id,
        )
    except (requests.RequestException, ValidationError) as exc:
        raise to_enable_banking_http_exception(exc) from exc

    return to_account_details_response(account)


@router.get(
    "/{account_id}/balances",
    response_model=AccountBalanceResponse,
    summary="Get account balances",
)
async def get_account_balance(
    account_id: str,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountBalanceResponse:
    account_link = await repository.get_account_owned_by_user(
        db, current_user.user_id, account_id
    )
    if account_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    try:
        balance = retrieve_account_balances(
            settings=settings,
            account_id=account_id,
        )
    except (requests.RequestException, ValidationError) as exc:
        raise to_enable_banking_http_exception(exc) from exc

    return to_account_balance_response(account_id, balance)


@router.get(
    "/{account_id}/transactions",
    response_model=AccountTransactionsResponse,
    summary="List account transactions",
)
async def get_account_transactions(
    account_id: str,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountTransactionsResponse:
    account_link = await repository.get_account_owned_by_user(
        db, current_user.user_id, account_id
    )
    if account_link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    await sync_transactions_for_account(db, account_id, since=date.today() - timedelta(days=7))

    transactions = await repository.get_transactions_for_account(db, account_id)
    return to_account_transactions_response(account_id, transactions)


@router.put(
    "/order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reorder accounts",
    dependencies=[Depends(verify_csrf)],
)
async def reorder_accounts(
    body: ReorderAccountsRequest,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    owned = await repository.get_all_owned_by_user(db, current_user.user_id)
    owned_ids = {account.account_id for account in owned}
    ordered = [account_id for account_id in body.account_ids if account_id in owned_ids]
    await repository.set_sort_orders(db, ordered)


@router.patch(
    "/{account_id}",
    response_model=RenameAccountResponse,
    summary="Rename account",
    dependencies=[Depends(verify_csrf)],
)
async def rename_account(
    account_id: str,
    body: RenameAccountRequest,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RenameAccountResponse:
    account = await repository.get_account_owned_by_user(db, current_user.user_id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    display_name = (body.display_name or "").strip() or None
    await repository.set_display_name(db, account_id, display_name)

    return RenameAccountResponse(account_id=account_id, display_name=display_name)