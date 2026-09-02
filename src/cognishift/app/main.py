import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import httpx
from fastapi import FastAPI
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
    yield
    # Cleanup on shutdown

app = FastAPI(
    title="CogniShift API",
    description="On-premise Agentic AI Workbench",
    version=__version__,
    lifespan=lifespan,
)

# Attempt to include routers, ignoring errors if they don't exist yet
try:
    from cognishift.app.api import workspaces
    app.include_router(workspaces.router)
except ImportError:
    pass

try:
    from cognishift.app.api import agents
    app.include_router(agents.router)
except ImportError:
    pass

try:
    from cognishift.app.api import knowledge
    app.include_router(knowledge.router)
except ImportError:
    pass

try:
    from cognishift.app.api import runs
    app.include_router(runs.router)
except ImportError:
    pass

try:
    from cognishift.app.api import approvals
    app.include_router(approvals.router)
except ImportError:
    pass


async def check_ollama() -> tuple[bool, List[Dict[str, Any]]]:
    """Check if Ollama is available and return models."""
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
    """Get system status."""
    ollama_available, available_models = await check_ollama()
    # Simple check if DB file exists (for now)
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
    """Get privacy and data location status."""
    external_blocked = settings.operating_mode == "local"
    return {
        "operating_mode": settings.operating_mode,
        "external_apis_blocked": external_blocked,
        "data_directory": str(settings.data_dir.absolute()),
        "explanation": "In local mode, all external API calls are blocked. Data is stored on-premise." if external_blocked else "External APIs may be used."
    }

@app.get("/api/v1/system/models")
async def list_models():
    """List available local models from Ollama."""
    _, available_models = await check_ollama()
    return available_models
