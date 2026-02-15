from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import upload, analytics, ai, export, admin, auth
from app.logging_config import setup_logging
from app.core.config import settings
import os

setup_logging()

app = FastAPI(title="InsightIQ - AI Business Intelligence Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event('startup')
def startup_event():
    os.makedirs(settings.upload_dir, exist_ok=True)
    from app.database import engine
    from app.models import metadata
    metadata.create_all(bind=engine)


app.include_router(upload.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get('/')
def index(request: Request):
    import time
    return templates.TemplateResponse("index.html", {"request": request, "now": int(time.time())})
