import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from cognishift.app.config import settings, PROJECT_ROOT
from cognishift.core.network.client import get_sovereign_async_client
from cognishift import __version__

# -----------------------------------------------------------------------------
# WINDOWS PROACTOR IOCP DISCONNECT RESILIENCE
# Silences benign WinError 10054 on sudden mobile/browser disconnects without crashing
# -----------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        import asyncio.proactor_events
        import socket

        _orig_call_connection_lost = asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost

        def _silenced_call_connection_lost(self, exc):
            if self._called_connection_lost:
                return
            try:
                self._protocol.connection_lost(exc)
            finally:
                if hasattr(self, "_sock") and self._sock is not None:
                    if hasattr(self._sock, "shutdown") and self._sock.fileno() != -1:
                        try:
                            self._sock.shutdown(socket.SHUT_RDWR)
                        except (OSError, ConnectionResetError):
                            pass
                    try:
                        self._sock.close()
                    except (OSError, ConnectionResetError):
                        pass
                    self._sock = None
                server = getattr(self, "_server", None)
                if server is not None:
                    server._detach()
                    self._server = None
                self._called_connection_lost = True

        asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost
    except Exception:
        pass


# Create data directories on startup
def create_directories():
    """Ensure all required data directories exist."""
    directories = [
        settings.data_dir,
        settings.data_dir.parent / settings.database_path.parent if not settings.database_path.is_absolute() else settings.database_path.parent,
        settings.chroma_path,
        settings.upload_dir,
        settings.data_dir / "alerts" / "mailbox",
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for FastAPI."""
    try:
        loop = asyncio.get_running_loop()
        _default_handler = loop.get_exception_handler()

        def _custom_exception_handler(current_loop, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
                return
            if exc and getattr(exc, "winerror", None) == 10054:
                return
            if _default_handler:
                _default_handler(current_loop, context)
            else:
                current_loop.default_exception_handler(context)

        loop.set_exception_handler(_custom_exception_handler)
    except Exception:
        pass

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

    # Restore active device sessions from database
    from cognishift.app.core.device_security import restore_active_device_sessions
    await restore_active_device_sessions()

    # Start local loopback SMTP server (127.0.0.1:1025) and flush outbox
    from cognishift.core.notifications import flush_pending_outbox, start_local_smtp_server, stop_local_smtp_server
    try:
        await start_local_smtp_server()
        await flush_pending_outbox()
        from cognishift.core.authorizations import process_pending_post_approval_jobs
        await process_pending_post_approval_jobs()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"Could not start local SMTP server or flush outbox: {exc}")
            
    yield

    try:
        await stop_local_smtp_server()
    except Exception:
        pass

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
        "https://localhost:8443",
        "https://127.0.0.1:8443",
        "https://10.10.182.228:8443",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject strict Content Security Policy and hardening headers."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        # Artifact previews are fetched with authenticated headers and exposed
        # to <img> elements through same-page object URLs.
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/static", "/assets")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


from cognishift.app.api import workspaces, agents, knowledge, runs, approvals, artifacts, sovereignty, sandbox, auth, audit, security_dashboard, authorizations, mail

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(agents.router)
app.include_router(knowledge.router)
app.include_router(runs.router)
app.include_router(approvals.router)
app.include_router(artifacts.router)
app.include_router(sovereignty.router)
app.include_router(sandbox.router)
app.include_router(audit.router)
app.include_router(security_dashboard.router)
app.include_router(authorizations.router)
app.include_router(mail.router)

# Setup Frontend UI (Tiered: Built Vite SPA -> Legacy Static -> API Welcome JSON)
vite_dist_dir = PROJECT_ROOT / "frontend" / "dist"
legacy_static_dir = PROJECT_ROOT / "src" / "cognishift" / "app" / "static"


if vite_dist_dir.exists() and (vite_dist_dir / "index.html").exists():
    if (vite_dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(vite_dist_dir / "assets")), name="vite_assets")

    @app.get("/")
    async def root_spa():
        return FileResponse(str(vite_dist_dir / "index.html"))

elif legacy_static_dir.exists() and (legacy_static_dir / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(legacy_static_dir)), name="static")

    @app.get("/")
    async def root_legacy():
        return RedirectResponse(url="/static/index.html")

else:
    @app.get("/")
    async def root_api():
        return {
            "app": "CogniShift API",
            "version": __version__,
            "status": "online",
            "operating_mode": settings.operating_mode,
            "docs": "/docs",
            "frontend": {
                "vite_dev_server": "http://127.0.0.1:5173",
                "note": "React 19 + Vite frontend available. Run 'npm run dev' or 'npm run build' in frontend/."
            }
        }

async def check_ollama() -> tuple[bool, List[Dict[str, Any]]]:
    try:
        async with get_sovereign_async_client(timeout=2.0, component="system_status") as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return True, data.get("models", [])
    except (httpx.RequestError, httpx.HTTPStatusError, Exception):
        return False, []

@app.get("/health")
async def health_check():
    """Standard health probe for local reverse proxies, LAN checks, and container health monitors."""
    return {"status": "ok", "version": __version__, "operating_mode": settings.operating_mode}


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
        "data_directory": "data"
    }

@app.get("/api/v1/system/models")
async def list_models():
    _, available_models = await check_ollama()
    return available_models


# React Router uses browser history paths. Serve the SPA shell for known client
# routes so refreshing /security, /operator, etc. does not become a backend 404.
# API, documentation, asset, and unknown file-like paths continue to fail closed.
_SPA_CLIENT_ROUTES = {
    "dashboard", "operator", "workspaces", "agents", "knowledge",
    "runs", "approvals", "artifacts", "security", "system", "mailbox",
}


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_history_fallback(full_path: str):
    first_segment = full_path.strip("/").split("/", 1)[0]
    if (
        vite_dist_dir.exists()
        and (vite_dist_dir / "index.html").exists()
        and first_segment in _SPA_CLIENT_ROUTES
    ):
        return FileResponse(str(vite_dist_dir / "index.html"))
    raise HTTPException(status_code=404, detail="Not Found")
