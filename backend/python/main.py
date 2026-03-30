from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import rooms, auth, spotify, playback
from api import websockets
import repositories.crud as crud

app = FastAPI()

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
    return {"status": "ok"}


@app.get("/hello")
async def root():
    return {"message": "Hello World"}


@app.get("/db-health")
async def db_health():
    result = await crud.check_db_health()
    return {"db-status": result.get("status"), **result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
