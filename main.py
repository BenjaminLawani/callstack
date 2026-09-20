from fastapi import FastAPI, Request

from contextlib import asynccontextmanager

from api.common.db import init_db
from api.common.config import templates

from api.auth.endpoints import (
    auth_router,
    profile_router
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield 

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"ping":"pong"}

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

app.include_router(auth_router)
app.include_router(profile_router)