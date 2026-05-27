from pydantic import BaseModel


class RoomRequest(BaseModel):
    """Request model for joining a room via its 6-character join code."""

    join_code: str
    user_id: str
    display_name: str


class CreateRoomRequest(BaseModel):
    """Request model for creating a room"""

    name: str
    user_id: str
    display_name: str
    supported_provider_id: str


class RoomResponse(BaseModel):
    """Response model for room management endpoints"""

    success: bool
    message: str
    room_id: str | None = None
    join_code: str | None = None


class Track(BaseModel):
    """Model representing a track/song"""

    trackId: str
    providerTrackId: str
    title: str
    artist: str
    album: str
    duration: int
    coverUrl: str
    deepLink: str


class UserInfo(BaseModel):
    """Model representing basic user information"""

    userId: str
    displayName: str
    createdAt: str


class Membership(BaseModel):
    """Model representing a user's membership in a room"""

    joinedAt: str
    leftAt: str | None = None
    membershipStatus: str


class UserEntry(BaseModel):
    """Model representing a user entry in the room's users list"""

    user: UserInfo
    membership: Membership


class Feedback(BaseModel):
    """Model representing feedback on a queue entry"""

    userId: str
    votedAt: str
    type: str  # "upvote" or "downvote"


class AddedBy(BaseModel):
    """Model representing who added a queue entry"""

    userId: str
    displayName: str


class QueueEntry(BaseModel):
    """Model representing a song entry in the queue"""

    queueEntryId: str
    track: Track
    addedBy: AddedBy
    queuedAt: str
    position: int
    status: str  # "queued", "playing", "skipped", etc.
    voteScore: int
    orderRank: int
    feedback: list[Feedback] = []


class Room(BaseModel):
    """Model representing room information"""

    roomId: str
    joinCode: str
    name: str
    status: str
    createdAt: str


class Host(BaseModel):
    """Model representing the host of a room"""

    userId: str
    displayName: str
    createdAt: str


class RoomState(BaseModel):
    """Model representing the complete state of a room"""

    room: Room
    host: Host
    users: list[UserEntry]
    queue: list[QueueEntry]
    lastEvent: dict[str, str] | None = None
    lastActivity: dict[str, object] | None = None


class AddQueueRequest(BaseModel):
    """Request model for adding a song to the queue"""

    type: str = "addqueue"
    room_id: str
    track: Track
    user_id: str


class LeaveRoomRequest(BaseModel):
    """Request model for leaving a room (identity only; no display name)."""

    room_id: str
    user_id: str


class DeleteRoomRequest(BaseModel):
    """Request model for deleting a room"""

    room_id: str
    user_id: str


class RoomAvailabilityRequest(BaseModel):
    """Request model for checking multiple room join codes."""

    join_codes: list[str]


class RoomAvailabilityResponse(BaseModel):
    """Response model listing which join codes are still joinable."""

    available_join_codes: list[str]
    unavailable_join_codes: list[str]
