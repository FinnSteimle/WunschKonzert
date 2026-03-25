from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Request model for authentication endpoints"""

    username: str
    password: str


class RoomRequest(BaseModel):
    """Request model for room management endpoints"""

    room_id: str
    user_id: str
    display_name: str


class CreateRoomRequest(BaseModel):
    """Request model for creating a room"""

    name: str
    user_id: str
    display_name: str
    supported_provider_id: str


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


class AddQueueRequest(BaseModel):
    """Request model for adding a song to the queue"""

    type: str = "addqueue"
    room_id: str
    track: Track
    user_id: str


class AddMusicProviderRequest(BaseModel):
    """Request model for adding a music provider to a user"""

    user_id: str
    provider_id: str
    external_user_id: str


class AddMusicProviderResponse(BaseModel):
    """Response model for adding a music provider"""

    success: bool
    message: str
    provider_account_id: str | None = None


class DeleteRoomRequest(BaseModel):
    """Request model for deleting a room"""

    room_id: str
    user_id: str


class VoteRequest(BaseModel):
    """Request model for voting on a queue entry"""

    user_id: str
    vote_type: str  # "upvote", "downvote", "neutral"


class PlaybackRequest(BaseModel):
    """Request model for playback controls"""

    user_id: str
    action: str  # "pause" or "resume"
