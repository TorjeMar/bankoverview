from fastapi import APIRouter

from app.features.accounts.router import router as accounts_router
from app.features.auth.router import router as auth_router
from app.features.connections.router import router as connections_router
from app.features.overview.router import router as overview_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(connections_router)
api_router.include_router(accounts_router)
api_router.include_router(overview_router)