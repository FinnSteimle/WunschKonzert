import os
import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database import (
    AccountStatus,
    FeedbackType,
    MembershipStatus,
    MusicProvider,
    PlaybackSession,
    PlaybackState,
    ProviderAccount,
    QueueEntry,
    QueueEntryStatus,
    Room,
    RoomMembership,
    RoomStatus,
    SongFeedback,
    Track,
    User,
)

# Create async engine and session factory lazily
# This allows tests to run without DATABASE_URL environment variable
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_database_url() -> str:
    """Get and format the database URL"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Please set it in your .env file or environment."
        )

    if not database_url.startswith("postgresql+asyncpg"):
        if database_url.startswith("postgresql:"):
            database_url = database_url.replace("postgresql:", "postgresql+asyncpg:", 1)
        else:
            database_url = "postgresql+asyncpg:" + database_url

    return database_url


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Initialize and return the session factory"""
    global _engine, _session_factory
    if _session_factory is None:
        database_url = _get_database_url()
        _engine = create_async_engine(database_url)
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_user(user_id: str) -> User | None:
    """Get user by ID or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        return await session.get(User, user_id)


async def get_room(room_id: str) -> Room | None:
    """Get room by ID or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        return await session.get(Room, room_id)


async def get_room_by_join_code(join_code: str) -> Room | None:
    """Get room by join code or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Room).where(Room.joinCode == join_code))
        return result.scalar_one_or_none()


async def get_room_membership(user_id: str, room_id: str) -> RoomMembership | None:
    """Get existing room membership or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(RoomMembership).where(
                RoomMembership.userId == user_id, RoomMembership.roomId == room_id
            )
        )
        return result.scalar_one_or_none()


async def create_room_membership(user_id: str, room_id: str) -> RoomMembership:
    """Create a new room membership"""
    # Check if membership already exists
    existing = await get_room_membership(user_id, room_id)
    if existing:
        raise ValueError("User is already a member of this room")

    session_factory = _get_session_factory()
    async with session_factory() as session:
        membership = RoomMembership(userId=user_id, roomId=room_id)
        session.add(membership)
        await session.commit()
        await session.refresh(membership)
        return membership


async def create_user(user_id: str, display_name: str) -> User:
    """Create a new user"""
    # Check if user already exists
    existing = await get_user(user_id)
    if existing:
        raise ValueError("User already exists")

    session_factory = _get_session_factory()
    async with session_factory() as session:
        user = User(userId=user_id, displayName=display_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def leave_room(user_id: str, room_id: str) -> RoomMembership:
    """Leave a room by setting leftAt timestamp"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(RoomMembership).where(
                RoomMembership.userId == user_id, RoomMembership.roomId == room_id
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise ValueError("User is not a member of this room")

        membership.leftAt = datetime.utcnow()  # type: ignore[attr-defined]
        membership.membershipStatus = MembershipStatus.INACTIVE  # type: ignore[attr-defined]
        await session.commit()
        await session.refresh(membership)
        return membership


def _generate_join_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    # Sampling from UUID bytes keeps generation deterministic and server-side.
    random_bytes = uuid.uuid4().bytes
    out = []
    for i in range(length):
        out.append(alphabet[random_bytes[i] % len(alphabet)])
    return "".join(out)


async def create_room(name: str, user_id: str, supported_provider_id: str) -> Room:
    """Create a new room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        room_id = str(uuid.uuid4())
        join_code = _generate_join_code()

        # Extremely unlikely collisions, but guaranteed unique before insert.
        while (
            await session.execute(select(Room).where(Room.joinCode == join_code))
        ).scalar_one_or_none() is not None:
            join_code = _generate_join_code()

        room = Room(
            roomId=room_id,
            joinCode=join_code,
            name=name,
            hostedBy=user_id,
            supportedProviderId=supported_provider_id,
            status=RoomStatus.ACTIVE,
        )
        session.add(room)
        await session.commit()
        await session.refresh(room)
        return room


async def create_provider_account(
    user_id: str, provider_id: str, external_user_id: str
) -> ProviderAccount:
    """Create a new provider account for a user"""
    # Check if user exists
    user = await get_user(user_id)
    if not user:
        raise ValueError("User not found")

    # Check if provider account already exists for this user and provider
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(
                f"User already has an account linked for provider {provider_id}"
            )

    # Create new provider account
    session_factory = _get_session_factory()
    async with session_factory() as session:
        provider_account = ProviderAccount(
            providerAccountId=str(uuid.uuid4()),
            externalUserId=external_user_id,
            userId=user_id,
            providerId=provider_id,
            status=AccountStatus.ACTIVE,
        )
        session.add(provider_account)
        await session.commit()
        await session.refresh(provider_account)
        return provider_account


async def get_music_provider(provider_id: str) -> MusicProvider | None:
    """Get music provider by ID or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        return await session.get(MusicProvider, provider_id)


async def create_music_provider(provider_id: str, name: str) -> MusicProvider:
    """Create a new music provider"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        # Check if provider already exists
        existing = await get_music_provider(provider_id)
        if existing:
            return existing

        provider = MusicProvider(providerId=provider_id, name=name)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        return provider


async def update_membership_status(
    user_id: str, room_id: str, status: MembershipStatus
) -> RoomMembership:
    """Update membership status for a user in a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(RoomMembership).where(
                RoomMembership.userId == user_id,
                RoomMembership.roomId == room_id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise ValueError("Membership not found")

        membership.membershipStatus = status
        if status == MembershipStatus.ACTIVE:
            membership.leftAt = None

        await session.commit()
        await session.refresh(membership)
        return membership


async def get_room_members(room_id: str) -> list[tuple[RoomMembership, User]]:
    """Get all active members of a room with their user data"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(RoomMembership, User)
            .join(User)
            .where(
                RoomMembership.roomId == room_id,
                RoomMembership.membershipStatus == MembershipStatus.ACTIVE,
            )
        )
        return result.all()


async def get_queue_entries(room_id: str) -> list[QueueEntry]:
    """Get all queue entries for a room, ordered by position"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
        )
        return result.scalars().all()


async def get_current_playback_session(room_id: str) -> PlaybackSession | None:
    """Get the current playback session for a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(PlaybackSession)
            .where(PlaybackSession.roomId == room_id)
            .order_by(PlaybackSession.startedAt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_track(track_id: str) -> DbTrack | None:
    """Get track by ID or return None if not found"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        return await session.get(DbTrack, track_id)


async def create_track(track_data: dict) -> DbTrack:
    """Create a new track"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        track = DbTrack(**track_data)
        session.add(track)
        await session.commit()
        await session.refresh(track)
        return track


async def create_queue_entry(queue_entry_data: dict) -> QueueEntry:
    """Create a new queue entry"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        queue_entry = QueueEntry(**queue_entry_data)
        session.add(queue_entry)
        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def get_queue_entry(queue_entry_id: str) -> QueueEntry | None:
    """Get queue entry by ID"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        return await session.get(QueueEntry, queue_entry_id)


async def update_queue_entry(queue_entry_id: str, updates: dict) -> QueueEntry:
    """Update a queue entry"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        queue_entry = await session.get(QueueEntry, queue_entry_id)
        if not queue_entry:
            raise ValueError("Queue entry not found")

        for key, value in updates.items():
            setattr(queue_entry, key, value)

        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def create_playback_session(playback_data: dict) -> PlaybackSession:
    """Create a new playback session"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        playback_session = PlaybackSession(**playback_data)
        session.add(playback_session)
        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def update_playback_session(
    playback_session_id: str, updates: dict
) -> PlaybackSession:
    """Update a playback session"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        playback_session = await session.get(PlaybackSession, playback_session_id)
        if not playback_session:
            raise ValueError("Playback session not found")

        for key, value in updates.items():
            setattr(playback_session, key, value)

        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def get_song_feedback_by_queue_entry(queue_entry_id: str) -> list[SongFeedback]:
    """Get all song feedback for a queue entry"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
            )
        )
        return result.scalars().all()


async def get_song_feedback(queue_entry_id: str, user_id: str) -> SongFeedback | None:
    """Get song feedback for a user"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
                SongFeedback.userId == user_id,
            )
        )
        return result.scalar_one_or_none()


async def create_or_update_song_feedback(feedback_data: dict) -> SongFeedback:
    """Create or update song feedback"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        existing = await get_song_feedback(
            feedback_data["queueEntryId"], feedback_data["userId"]
        )

        if existing:
            for key, value in feedback_data.items():
                setattr(existing, key, value)
            feedback = existing
        else:
            feedback = SongFeedback(**feedback_data)
            session.add(feedback)

        await session.commit()
        await session.refresh(feedback)
        return feedback


async def delete_song_feedback(queue_entry_id: str, user_id: str) -> None:
    """Delete song feedback"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        feedback = await get_song_feedback(queue_entry_id, user_id)
        if feedback:
            await session.delete(feedback)
            await session.commit()


async def get_max_queue_position(room_id: str) -> int:
    """Get the maximum queue position for a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import func, select

        result = await session.execute(
            select(func.max(QueueEntry.position)).where(QueueEntry.roomId == room_id)
        )
        max_position = result.scalar_one_or_none()
        return int(max_position or 0)


async def get_playing_queue_entry(room_id: str) -> QueueEntry | None:
    """Get the currently playing queue entry for a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(QueueEntry)
            .where(
                QueueEntry.roomId == room_id,
                QueueEntry.status == QueueEntryStatus.PLAYING,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_first_queued_entry(room_id: str) -> QueueEntry | None:
    """Get the first queued entry for a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_room_memberships(room_id: str) -> list[RoomMembership]:
    """Get all memberships for a room"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(RoomMembership).where(RoomMembership.roomId == room_id)
        )
        return result.scalars().all()


async def update_room_status(room_id: str, status: RoomStatus) -> Room:
    """Update room status"""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        room = await session.get(Room, room_id)
        if not room:
            raise ValueError("Room not found")

        room.status = status
        await session.commit()
        await session.refresh(room)
        return room


async def check_db_health() -> dict:
    """Check if database is healthy by executing a simple query"""
    try:
        session_factory = _get_session_factory()
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "ok"}
        return {"status": "error", "detail": "Query returned unexpected result"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
