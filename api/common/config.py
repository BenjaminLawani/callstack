import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

from fastapi.templating import Jinja2Templates

templates_path = Path(__file__).resolve().parents[2] / "frontend"
templates = Jinja2Templates(templates_path)

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.environ["DATABASE_URL"]
    JWT_KEY: str = os.environ["JWT_KEY"]
    GOOGLE_CLIENT_ID: str = os.environ["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET: str = os.environ["GOOGLE_CLIENT_SECRET"]
    GOOGLE_REDIRECT_URL: str = os.environ["GOOGLE_REDIRECT_URL"]
    DEBUG: bool = os.environ["DEBUG"]
    ACCESS_TOKEN_EXPIRES: int = os.environ["ACCESS_TOKEN_EXPIRES"]
    REFRESH_TOKEN_EXPIRES: int = os.environ["REFRESH_TOKEN_EXPIRES"]

    R2_ACCOUNT_ID: str = os.environ["R2_ACCOUNT_ID"]
    R2_ACCESS_KEY_ID: str = os.environ["R2_ACCESS_KEY_ID"]
    R2_SECRET_KEY: str = os.environ["R2_SECRET_KEY"]
    R2_BUCKET_NAME: str = os.environ["R2_BUCKET_NAME"]
    R2_PUBLIC_URL: str = os.environ["R2_PUBLIC_URL"]

    ASSEMBLYAI_API_KEY: str = os.environ["ASSEMBLYAI_API_KEY"]
    LLM_GATEWAY_URL: str = os.environ.get(
        "LLM_GATEWAY_URL", "https://llm-gateway.assemblyai.com/v1"
    )

settings = Settings()