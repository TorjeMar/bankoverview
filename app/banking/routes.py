from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.auth.types import PendingAuthorization, UserSession
from app.banking.dependencies import get_bank_connection
from app.banking.service import (
    save_bank_connection,
    to_bank_connection_response,
)
from app.banking.types import (
    AccountsResponse,
    BankConnection,
    CallbackResponse,
    StartAuthorizationResponse,
)
from app.config import settings
from app.enable_banking.client import (
    create_bank_authorization,
    exchange_authorization_code,
    retrieve_enable_banking_session,
)
from app.storage.memory import pending_authorizations

router = APIRouter(tags=["banking"])


@router.post(
    "/start",
    response_model=StartAuthorizationResponse,
)
def start_auth(
    current_user: Annotated[
        UserSession,
        Depends(get_current_user),
    ],
) -> StartAuthorizationResponse:
    state = str(uuid4())

    pending_authorizations[state] = PendingAuthorization(
        user_id=current_user.user_id,
        app_session_id=current_user.app_session_id,
        created_at=datetime.now(timezone.utc),
        status="pending",
    )

    try:
        authorization_url = create_bank_authorization(
            settings=settings,
            state=state,
        )
    except requests.RequestException as exc:
        pending_authorizations.pop(state, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to initiate bank authorization: {exc}",
        ) from exc
    except ValueError as exc:
        pending_authorizations.pop(state, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return StartAuthorizationResponse(
        authorization_url=authorization_url
    )


@router.get(
    "/callback",
    response_model=CallbackResponse,
)
def callback(
    state: str,
    code: str,
    current_user: Annotated[
        UserSession,
        Depends(get_current_user),
    ],
) -> CallbackResponse:
    pending_auth = pending_authorizations.get(state)

    if pending_auth is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    if pending_auth.app_session_id != current_user.app_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Authorization state does not belong "
                "to this app session"
            ),
        )

    if pending_auth.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization state does not belong to this user",
        )

    if pending_auth.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization state has already been consumed",
        )

    if (
        datetime.now(timezone.utc) - pending_auth.created_at
        > timedelta(minutes=10)
    ):
        pending_authorizations.pop(state, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization state has expired",
        )

    pending_auth.status = "processing"

    try:
        session = exchange_authorization_code(
            settings=settings,
            code=code,
        )
        connection = save_bank_connection(
            user_id=current_user.user_id,
            session=session,
        )
    except requests.RequestException as exc:
        pending_auth.status = "failed"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        ) from exc
    except ValidationError as exc:
        pending_auth.status = "failed"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Enable Banking returned an invalid "
                "session response"
            ),
        ) from exc

    pending_authorizations.pop(state, None)

    return CallbackResponse(
        message="Bank connection established successfully",
        connection=to_bank_connection_response(connection),
    )


@router.get(
    "/accounts",
    response_model=AccountsResponse,
)
def get_accounts(
    connection: Annotated[
        BankConnection,
        Depends(get_bank_connection),
    ],
) -> AccountsResponse:
    try:
        session = retrieve_enable_banking_session(
            settings=settings,
            session_id=connection.enable_banking_session_id,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve accounts",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Enable Banking returned invalid session data",
        ) from exc

    return AccountsResponse(accounts=session.accounts)
