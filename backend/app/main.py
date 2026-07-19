"""FastAPI backend: JSON API under /api/*, health at /healthz, and the built
React SPA served from ./static at / (API routes are registered first, so they
take precedence over the SPA catch-all at the bottom)."""

import logging
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI(title="fastapi-react-app")


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
if _static.is_dir():
    # Real files (Vite's hashed JS/CSS bundles) — served directly by the mount.
    if (_static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Unknown /api/* paths stay JSON 404s — never HTML.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Root-level real files (favicon, robots.txt, …) if they exist;
        # resolve() + is_relative_to() guards against path traversal.
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static):
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
