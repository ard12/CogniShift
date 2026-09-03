import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from cognishift.app.config import settings
from cognishift import __version__

# Create data directories on startup
def create_directories():
    """Ensure all required data directories exist."""
    directories = [
        settings.data_dir,
        settings.data_dir.parent / settings.database_path.parent if not settings.database_path.is_absolute() else settings.database_path.parent,
        settings.chroma_path,
        settings.upload_dir,
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for FastAPI."""
    create_directories()
    # Initialize database tables
    from cognishift.app.db.database import init_db
    await init_db()
    
    # Ensure a default workspace exists for the UI
    from cognishift.app.db.database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM workspaces WHERE id = 1")
        if not await cursor.fetchone():
            await db.execute("INSERT INTO workspaces (id, name, description) VALUES (1, 'Main Refinery Workspace', 'Default workspace')")
            await db.commit()
            
    yield

app = FastAPI(
    title="CogniShift API",
    description="On-premise Agentic AI Workbench",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


from cognishift.app.api import workspaces, agents, knowledge, runs, approvals

app.include_router(workspaces.router)
app.include_router(agents.router)
app.include_router(knowledge.router)
app.include_router(runs.router)
app.include_router(approvals.router)

# Setup Static UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

async def check_ollama() -> tuple[bool, List[Dict[str, Any]]]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return True, data.get("models", [])
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False, []

@app.get("/api/v1/system/status")
async def system_status():
    ollama_available, available_models = await check_ollama()
    db_initialized = settings.database_path.exists()
    return {
        "operating_mode": settings.operating_mode,
        "ollama_available": ollama_available,
        "available_models": available_models,
        "database_initialized": db_initialized,
        "version": __version__
    }

@app.get("/api/v1/system/privacy-status")
async def privacy_status():
    external_blocked = settings.operating_mode == "local"
    return {
        "operating_mode": settings.operating_mode,
        "external_apis_blocked": external_blocked,
        "data_directory": str(settings.data_dir.absolute())
    }

@app.get("/api/v1/system/models")
async def list_models():
    _, available_models = await check_ollama()
    return available_models
