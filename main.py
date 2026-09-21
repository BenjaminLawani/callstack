from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

from api.common.db import init_db
from api.common.config import templates, templates_path

from api.auth.endpoints import (
    auth_router,
    profile_router
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield 

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"ping":"pong"}

@app.get("/", include_in_schema=False)
def home_page(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/pipelines", include_in_schema=False)
def pipelines_page(request: Request):
    return templates.TemplateResponse(request, "pipelines.html")

@app.get("/test-cases", include_in_schema=False)
def test_cases_page(request: Request):
    return templates.TemplateResponse(request, "test_cases.html")

@app.get("/projects", include_in_schema=False)
def projects_page(request: Request):
    return templates.TemplateResponse(request, "projects.html")

@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/onboarding", include_in_schema=False)
def onboarding_page(request: Request):
    return templates.TemplateResponse(request, "onboarding.html")

app.mount("/assets", StaticFiles(directory=templates_path / "assets"), name="assets")

app.include_router(auth_router)
app.include_router(profile_router)
