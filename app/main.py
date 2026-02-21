from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import upload, analytics, ai, export, admin, auth
from app.logging_config import setup_logging
from app.core.config import settings
import logging
import os

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="InsightIQ - AI Business Intelligence Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event('startup')
def startup_event():
    from dotenv import load_dotenv
    load_dotenv()
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info("App startup in %s mode", settings.app_env)

    if settings.app_env.lower() in {"production", "staging"}:
        if settings.jwt_secret == "replace_this_secret" or len(settings.jwt_secret) < 24:
            raise RuntimeError("JWT_SECRET is too weak for production/staging.")
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required in production/staging.")


app.include_router(upload.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get('/')
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
