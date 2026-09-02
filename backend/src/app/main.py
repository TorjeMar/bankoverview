from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    application = FastAPI(
        title="Personal Finance Dashboard API",
        version="0.1.0",
    )

    application.include_router(api_router)
    application.mount("/dev", StaticFiles(directory=STATIC_DIR, html=True), name="dev-ui")

    return application


app = create_app()