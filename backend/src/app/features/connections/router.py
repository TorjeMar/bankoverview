from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db, pending_authorizations
from app.features.accounts import repository as accounts_repository
from app.features.auth.router import get_current_user
from app.features.auth.schemas import UserSession
from app.features.connections import repository
from app.features.connections.models import BankConnectionModel
from app.features.connections.schemas import (
    CallbackResponse,
    PendingAuthorization,
    StartAuthorizationResponse,
)
from app.features.connections.service import (
    revoke_bank_connection,
    save_bank_connection,
    to_bank_connection_response,
)
from app.integrations.enable_banking.client import (
    create_bank_authorization,
    exchange_authorization_code,
)

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
)


async def get_bank_connection(
    current_user: Annotated[
        UserSession,
        Depends(get_current_user),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankConnectionModel:
    connection = await repository.get_active_for_user(db, current_user.user_id)

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active bank connections found for this user",
        )

    return connection


@router.post(
    "/start",
    response_model=StartAuthorizationResponse,
    summary="Start bank authorization",
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
        created_at=datetime.now(UTC),
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
    summary="Handle bank authorization callback",
)
async def callback(
    state: str,
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CallbackResponse:
    pending_auth = pending_authorizations.get(state)

    if pending_auth is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    if pending_auth.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization state has already been consumed",
        )

    authorization_age = (
        datetime.now(UTC) - pending_auth.created_at
    )

    if authorization_age > timedelta(minutes=10):
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

        connection = await save_bank_connection(
            db=db,
            user_id=pending_auth.user_id,
            session=session,
        )

    except requests.RequestException as exc:
        pending_authorizations.pop(state, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        ) from exc

    except ValidationError as exc:
        pending_authorizations.pop(state, None)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Enable Banking returned invalid session data",
                "errors": exc.errors(),
            },
        ) from exc

    except ValueError as exc:
        pending_authorizations.pop(state, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    pending_authorizations.pop(state, None)

    return CallbackResponse(
        message="Bank connection established successfully",
        connection=to_bank_connection_response(
            connection, account_count=len(session.accounts)
        ),
    )

@router.delete(
    "/revoke",
    response_model=CallbackResponse,
    summary="Revoke bank connection",
)
async def revoke_connection(
    connection: Annotated[BankConnectionModel, Depends(get_bank_connection)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CallbackResponse:
    accounts = await accounts_repository.get_for_connection(db, connection.connection_id)
    await revoke_bank_connection(db, connection)

    return CallbackResponse(
        message="Bank connection revoked successfully",
        connection=to_bank_connection_response(connection, account_count=len(accounts)),
    )