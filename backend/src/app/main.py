from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    application = FastAPI(
        title="Personal Finance Dashboard API",
        version="0.1.0",
    )

    # Needed by Authlib's OAuth client to hold short-lived state/nonce
    # values during the Google login redirect handshake — unrelated to
    # this app's own JWT session, which is stateless.
    application.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

    application.include_router(api_router)
    application.mount("/dev", StaticFiles(directory=STATIC_DIR, html=True), name="dev-ui")

    return application


app = create_app()