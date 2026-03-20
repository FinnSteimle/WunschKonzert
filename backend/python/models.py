from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Request model for authentication endpoints"""

    username: str
    password: str


class RoomRequest(BaseModel):
    """Request model for room management endpoints"""

    room_id: str
    user_id: str


class AuthResponse(BaseModel):
    """Response model for authentication endpoints"""

    success: bool
    message: str
    token: str | None = None


class RoomResponse(BaseModel):
    """Response model for room management endpoints"""

    success: bool
    message: str
    room_id: str | None = None
