from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import repositories.crud as crud
from api import websockets
from api.routers import auth, playback, rooms, spotify

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
