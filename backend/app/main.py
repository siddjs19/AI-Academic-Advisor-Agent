"""FastAPI app: JSON API under /api, the built React SPA everywhere else."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .api import router
from .config import settings
from .db import SessionLocal, init_db

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.auto_seed:
        from . import models, seed

        with SessionLocal() as db:
            if db.scalars(select(models.User).limit(1)).first() is None:
                seed.seed(db)
    yield


app = FastAPI(title="PrepPilot AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(404, "not found")
    if DIST.exists():
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(str(candidate))
        return FileResponse(str(DIST / "index.html"))
    raise HTTPException(404, "frontend not built — run `npm --prefix frontend run build`")
