from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.types import UserSession
from app.banking.types import BankConnection
from app.storage.memory import bank_connections


def get_bank_connection(
    current_user: Annotated[UserSession, Depends(get_current_user)],
) -> BankConnection:
    connections = bank_connections.get(current_user.user_id, [])

    if not connections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No bank connections found for this user",
        )

    active_connections = [
        connection
        for connection in connections
        if connection.status == "authorized"
    ]

    if not active_connections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active bank connections found for this user",
        )

    connection = active_connections[0]

    if (
        connection.valid_until is not None
        and connection.valid_until <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank connection has expired",
        )

    return connection
