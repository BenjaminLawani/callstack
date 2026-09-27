from pathlib import Path
import api.common.registry #noqa
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

from api.common.db import init_db
from api.common.config import templates, templates_path

from api.auth.endpoints import (
    auth_router,
    profile_router
)
from api.dashboard.endpoints import dashboard_router
from api.projects.endpoints import project_router
from api.pipelines.endpoints import (
    model_router,
    pipeline_router,
    node_router,
    runs_router
)
from api.test_cases.endpoints import test_cases_router
from api.metrics.endpoints import transcription_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield 

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"ping":"pong"}

@app.get("/", include_in_schema=False)
def landing_page(request: Request):
    return templates.TemplateResponse(request, "landing.html")

@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/onboarding", include_in_schema=False)
def onboarding_page(request: Request):
    return templates.TemplateResponse(request, "onboarding.html")

app.mount("/assets", StaticFiles(directory=templates_path / "assets"), name="assets")

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(dashboard_router)
app.include_router(project_router)
app.include_router(model_router)
app.include_router(node_router)
app.include_router(pipeline_router)
app.include_router(runs_router)
app.include_router(test_cases_router)
app.include_router(transcription_router)