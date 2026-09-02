from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.core.config import settings
from app.features.accounts.schemas import (
    AccountBalanceResponse,
    AccountDetailsResponse,
    AccountsResponse,
    AccountTransactionResponse,
    AccountTransactionsResponse,
)
from app.features.accounts.service import (
    to_account_balance_response,
    to_account_details_response,
    to_account_transaction_response,
    to_account_transactions_response,
    to_get_accounts_response,
)
from app.features.connections.models import BankConnectionModel
from app.features.connections.router import get_bank_connection
from app.integrations.enable_banking.client import (
    retrieve_account_balances,
    retrieve_account_details,
    retrieve_account_transaction,
    retrieve_account_transactions,
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
def get_account_details(
    account_id: str,
    connection: Annotated[
        BankConnectionModel,
        Depends(get_bank_connection),
    ],
) -> AccountDetailsResponse:
    if account_id not in connection.account_ids:
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
def get_account_balance(
    account_id: str,
    connection: Annotated[
        BankConnectionModel,
        Depends(get_bank_connection),
    ],
) -> AccountBalanceResponse:
    if account_id not in connection.account_ids:
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
def get_account_transactions(
    account_id: str,
    connection: Annotated[
        BankConnectionModel,
        Depends(get_bank_connection),
    ],
) -> AccountTransactionsResponse:
    if account_id not in connection.account_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    try:
        transactions = retrieve_account_transactions(
            settings=settings,
            account_id=account_id,
        )
    except (requests.RequestException, ValidationError) as exc:
        raise to_enable_banking_http_exception(exc) from exc

    return to_account_transactions_response(account_id, transactions)