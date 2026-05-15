import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import repositories.health_repo as health_repo
import repositories.music_provider_repo as music_provider_repo
from api import websockets
from api.routers import auth, debug, playback, provider_search, rooms, spotify_auth
from core.exceptions import ResourceNotFoundError


async def initialize_music_providers() -> None:
    """Seed default music providers on startup"""
    default_providers = [
        ("spotify", "Spotify"),
    ]

    for provider_id, name in default_providers:
        try:
            await music_provider_repo.get_music_provider(provider_id)
            # Provider already exists
        except ResourceNotFoundError:
            # Provider doesn't exist, create it
            await music_provider_repo.create_music_provider(provider_id, name)


def run_migrations() -> None:
    """Run database migrations using alembic"""
    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent,
        )
        if result.returncode != 0:
            print(f"Migration failed: {result.stderr}")
            sys.exit(1)
        print("Database migrations completed successfully")
    except Exception as e:
        print(f"Error running migrations: {e}")
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    run_migrations()
    await initialize_music_providers()
    yield
    # Shutdown (if needed)


app = FastAPI(lifespan=lifespan)

# Permissive CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms.router)
app.include_router(auth.router)
app.include_router(provider_search.router)
app.include_router(playback.router)
app.include_router(spotify_auth.router)
app.include_router(websockets.router)

# Include debug router in development, staging or if load testing is explicitly enabled
if (
    os.getenv("ENVIRONMENT") in ("development", "staging")
    or os.getenv("ENABLE_DEBUG_ROUTES", "").lower() == "true"
):
    app.include_router(debug.router)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health() -> JSONResponse:
    result = await health_repo.check_db_health()
    if result["status"] != "ok":
        return JSONResponse({"status": "error", "db": result}, status_code=503)
    return JSONResponse({"status": "ok", "db": result})


@app.get("/hello")
async def root() -> dict[str, str]:
    return {"message": "hello"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
