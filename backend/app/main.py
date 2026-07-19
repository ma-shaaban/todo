"""FastAPI backend: JSON API under /api/*, health at /healthz, and the built
React SPA served from ./static at / (API routes are registered first, so they
take precedence over the SPA catch-all at the bottom)."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.routers import auth as auth_router
from app.routers import notifications as notifications_router
from app.routers import push as push_router
from app.routers import spaces as spaces_router
from app.routers import todos as todos_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Reminder poller — one asyncio task in the single replica. Tests (and
    # any future multi-process setup) opt out via DISABLE_SCHEDULER=1.
    if os.environ.get("DISABLE_SCHEDULER") == "1":
        yield
        return
    from app.services.scheduler import run_poller

    stop = asyncio.Event()
    task = asyncio.create_task(run_poller(stop))
    try:
        yield
    finally:
        stop.set()
        try:
            # Bounded: a push send stuck in a worker thread must not wedge
            # pod shutdown until the SIGKILL.
            await asyncio.wait_for(task, timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            logger.warning("reminder poller did not stop in time — cancelled")


app = FastAPI(title="fastapi-react-app", lifespan=_lifespan)


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    """Reject state-changing requests whose Origin doesn't match the host.
    With SameSite=Lax session cookies this blocks cross-site form posts;
    requests without an Origin header (curl, same-origin GETs) pass."""
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        origin = request.headers.get("origin")
        if origin:
            origin_host = urlparse(origin).hostname
            request_host = (request.headers.get("host") or "").split(":")[0]
            # An unparseable Origin (including the literal "null" from
            # sandboxed iframes) is definitively cross-origin — fail closed.
            if origin_host is None or not request_host or origin_host != request_host:
                return JSONResponse(
                    status_code=403, content={"detail": "Cross-origin request rejected"}
                )
    return await call_next(request)


@app.exception_handler(OperationalError)
@app.exception_handler(ProgrammingError)
async def _db_error_handler(request: Request, exc: Exception):
    """DB unreachable or schema not migrated yet (entrypoint.sh keeps retrying
    migrations in the background). Same posture as /api/db-check: generic JSON,
    details only in server logs — and never a text/plain 500 on /api/*."""
    logger.exception("database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503, content={"detail": "Service temporarily unavailable — try again shortly"}
    )


def _db_conninfo() -> dict:
    """Connection parameters from the platform `app-db` Secret env contract."""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "postgres"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "connect_timeout": 3,
    }


@app.get("/api/hello")
def hello():
    return {"message": "Hello from FastAPI"}


@app.get("/api/db-check")
def db_check():
    """Round-trip to the database: SELECT now(). 503 if the DB is unreachable."""
    try:
        with psycopg.connect(**_db_conninfo()) as conn, conn.cursor() as cur:
            cur.execute("SELECT now()")
            (now,) = cur.fetchone()
        return {"db": "ok", "now": now.isoformat()}
    except Exception:
        # Template note: never return raw exception text to clients — DB errors
        # can leak hosts, role names or connection details. Log the full
        # traceback server-side (visible in `kubectl logs`) and keep the
        # client-facing body generic.
        logger.exception("/api/db-check failed")
        return JSONResponse(status_code=503, content={"db": "error", "hint": "see pod logs"})


@app.get("/api/version")
def version():
    # APP_VERSION is baked into the image at build time (Dockerfile ARG VERSION);
    # "dev" outside the container.
    return {"version": os.environ.get("APP_VERSION", "dev")}


@app.get("/healthz")
def healthz():
    """Readiness: process is up. Deliberately DB-free — a brief DB outage must
    not take the pod out of rotation (the SPA and /api/hello still work)."""
    return {"status": "ok"}


# Feature routers — registered here, above the SPA catch-all, per the house
# rule that API routes precede it (implementations live in app/routers/).
app.include_router(auth_router.router)
app.include_router(spaces_router.router)
app.include_router(todos_router.router)
app.include_router(push_router.router)
app.include_router(notifications_router.router)


# SPA serving — registered last so every /api/* + /healthz route above wins.
# The static directory only exists in the container image (built by the
# Dockerfile frontend stage); in local dev run the Vite dev server instead
# (it proxies /api → :8080).
#
# NB: StaticFiles(html=True) alone is NOT SPA-friendly — for a missing path
# Starlette serves 404.html (if present) or a plain 404, NOT index.html, so
# refreshing a client-side route like /settings would break. Instead: mount
# the real asset files, then a catch-all route that returns index.html for
# every non-/api, non-file GET path (the client-side router takes it from
# there).
_static = Path(__file__).resolve().parent.parent / "static"


def _resolve_static_file(full_path: str) -> Path | None:
    """A real file under the static root (any depth — icons/, sw.js, …), or
    None. resolve() + is_relative_to() guards against path traversal."""
    if not full_path:
        return None
    candidate = (_static / full_path).resolve()
    if candidate.is_file() and candidate.is_relative_to(_static):
        return candidate
    return None


if _static.is_dir():
    # Real files (Vite's hashed JS/CSS bundles) — served directly by the mount.
    if (_static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Unknown /api/* paths stay JSON 404s — never HTML.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Root-level and nested real files (favicon, manifest, icons, sw.js).
        candidate = _resolve_static_file(full_path)
        if candidate is not None:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
