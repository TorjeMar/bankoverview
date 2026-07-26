from fastapi import FastAPI

from app.auth.routes import router as auth_router
from app.banking.routes import router as banking_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(banking_router)
