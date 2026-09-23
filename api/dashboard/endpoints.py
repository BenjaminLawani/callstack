from fastapi import (
    APIRouter,
    Request
)

from api.common.config import templates

dashboard_router = APIRouter(
    tags=["DASHBOARD"],
    include_in_schema=False
)

@dashboard_router.get("/home")
def home_page(request: Request):
    return templates.TemplateResponse(request, "index.html")

@dashboard_router.get("/pipelines")
def pipelines_page(request: Request):
    return templates.TemplateResponse(request, "pipelines.html")

@dashboard_router.get("/test-cases")
def test_cases_page(request: Request):
    return templates.TemplateResponse(request, "test_cases.html")

@dashboard_router.get("/projects")
def projects_page(request: Request):
    return templates.TemplateResponse(request, "projects.html")

@dashboard_router.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html")
