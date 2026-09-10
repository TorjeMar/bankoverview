from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.core.config import settings
from app.database import get_db, pending_authorizations
from app.features.accounts import repository as accounts_repository
from app.features.auth.router import get_current_user, verify_csrf
from app.features.auth.schemas import UserSession
from app.features.connections import repository
from app.features.connections.models import BankConnectionModel
from app.features.connections.schemas import (
    BankOption,
    CallbackResponse,
    PendingAuthorization,
    StartAuthorizationRequest,
    StartAuthorizationResponse,
)
from app.features.connections.service import (
    backfill_bank_connection,
    create_bank_connection,
    revoke_bank_connection,
    to_bank_connection_response,
)
from app.integrations.enable_banking.client import (
    create_bank_authorization,
    exchange_authorization_code,
    list_aspsps,
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


async def get_connection_by_id(
    connection_id: str,
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankConnectionModel:
    connection = await repository.get_by_id_for_user(db, current_user.user_id, connection_id)

    if connection is None or connection.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank connection not found",
        )

    return connection


@router.get("/banks", response_model=list[BankOption], summary="List connectable banks")
def list_banks(
    current_user: Annotated[UserSession, Depends(get_current_user)],
) -> list[BankOption]:
    try:
        aspsps = list_aspsps(settings, country=settings.aspsp_country)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list banks: {exc}",
        ) from exc

    return [
        BankOption(name=a["name"], country=a.get("country", settings.aspsp_country))
        for a in aspsps
    ]


@router.post(
    "/start",
    response_model=StartAuthorizationResponse,
    summary="Start bank authorization",
    dependencies=[Depends(verify_csrf)],
)
def start_auth(
    current_user: Annotated[
        UserSession,
        Depends(get_current_user),
    ],
    body: StartAuthorizationRequest | None = None,
) -> StartAuthorizationResponse:
    state = str(uuid4())
    bank_name = (body.bank_name if body else None) or settings.aspsp_name
    bank_country = (body.bank_country if body else None) or settings.aspsp_country

    pending_authorizations[state] = PendingAuthorization(
        user_id=current_user.user_id,
        created_at=datetime.now(UTC),
        status="pending",
        bank_name=bank_name,
        bank_country=bank_country,
    )

    try:
        authorization_url = create_bank_authorization(
            settings=settings,
            state=state,
            aspsp_name=bank_name,
            aspsp_country=bank_country,
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
    summary="Handle bank authorization callback",
)
async def callback(
    state: str,
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    # Reached only via a full-page browser redirect from Enable Banking
    # (never called via fetch), so every exit has to land the user back in
    # the app — never a raw JSON error response.
    pending_auth = pending_authorizations.get(state)

    if pending_auth is None:
        return RedirectResponse(url="/app/?connection=invalid_state")

    if pending_auth.status != "pending":
        return RedirectResponse(url="/app/?connection=invalid_state")

    authorization_age = (
        datetime.now(UTC) - pending_auth.created_at
    )

    if authorization_age > timedelta(minutes=10):
        pending_authorizations.pop(state, None)
        return RedirectResponse(url="/app/?connection=invalid_state")

    pending_auth.status = "processing"

    try:
        session = exchange_authorization_code(
            settings=settings,
            code=code,
        )

        await create_bank_connection(
            db=db,
            user_id=pending_auth.user_id,
            session=session,
            bank_name=pending_auth.bank_name,
            bank_country=pending_auth.bank_country,
        )
        background_tasks.add_task(
            backfill_bank_connection,
            [account.uid for account in session.accounts],
        )

    except requests.RequestException:
        pending_authorizations.pop(state, None)
        return RedirectResponse(url="/app/?connection=provider_error")

    except ValidationError:
        pending_authorizations.pop(state, None)
        return RedirectResponse(url="/app/?connection=malformed")

    except ValueError:
        pending_authorizations.pop(state, None)
        return RedirectResponse(url="/app/?connection=provider_error")

    pending_authorizations.pop(state, None)

    return RedirectResponse(url="/app/?connection=success")

@router.delete(
    "/{connection_id}",
    response_model=CallbackResponse,
    summary="Revoke bank connection",
    dependencies=[Depends(verify_csrf)],
)
async def revoke_connection(
    connection: Annotated[BankConnectionModel, Depends(get_connection_by_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CallbackResponse:
    accounts = await accounts_repository.get_for_connection(db, connection.connection_id)
    await revoke_bank_connection(db, connection)

    return CallbackResponse(
        message="Bank connection revoked successfully",
        connection=to_bank_connection_response(connection, account_count=len(accounts)),
    )