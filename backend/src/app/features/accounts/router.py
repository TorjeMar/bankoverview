from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.features.accounts import repository
from app.features.accounts.schemas import (
    RenameAccountRequest,
    RenameAccountResponse,
    ReorderAccountsRequest,
)
from app.features.auth.router import get_current_user, verify_csrf
from app.features.auth.schemas import UserSession

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
)


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
