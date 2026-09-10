from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.features.auth.router import get_current_user, verify_csrf
from app.features.auth.schemas import UserSession
from app.features.connections import repository as connections_repository
from app.features.overview.schemas import OverviewResponse, SyncResponse
from app.features.overview.service import build_overview, sync_connections

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse, summary="Dashboard overview")
async def get_overview(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> OverviewResponse:
    connections = await connections_repository.get_all_active_for_user(db, current_user.user_id)
    return await build_overview(db, connections, days)


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Refresh balances and recent transactions from the bank",
    dependencies=[Depends(verify_csrf)],
)
async def sync_now(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncResponse:
    connections = await connections_repository.get_all_active_for_user(db, current_user.user_id)
    return await sync_connections(db, connections)
