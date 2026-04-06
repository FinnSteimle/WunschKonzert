import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import repositories.crud as crud
from api import websockets
from api.routers import auth, playback, rooms, spotify
from core.exceptions import ResourceNotFoundError


async def initialize_music_providers():
    """Seed default music providers on startup"""
    default_providers = [
        ("spotify", "Spotify"),
    ]

    for provider_id, name in default_providers:
        try:
            await crud.get_music_provider(provider_id)
            # Provider already exists
        except ResourceNotFoundError:
            # Provider doesn't exist, create it
            await crud.create_music_provider(provider_id, name)


def run_migrations():
    """Run database migrations using alembic"""
    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd="/app",
        )
        if result.returncode != 0:
            print(f"Migration failed: {result.stderr}")
            sys.exit(1)
        print("Database migrations completed successfully")
    except Exception as e:
        print(f"Error running migrations: {e}")
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(spotify.router)
app.include_router(playback.router)
app.include_router(websockets.router)


@app.get("/health")
async def health():
    result = await crud.check_db_health()
    if result["status"] != "ok":
        return JSONResponse({"status": "error", "db": result}, status_code=503)
    return {"status": "ok", "db": result}


@app.get("/hello")
async def root():
    return {"message": "Hello World"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
