import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import Row, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
)
from core.identifiers import generate_join_code, generate_room_id
from models.domain import (
    AccountStatus,
    MembershipStatus,
    MusicProvider,
    PlaybackSession,
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


async def create_user(
    user_id: str, display_name: str, session: AsyncSession | None = None
) -> User:
    # Create a session recursively, to avoid duplicating the method logic or burying it in an if/else
    # for both cases (session has been created and needs to be created)
    if session is None:
        session_factory = get_session_factory()
        # Closes the newly opened session after finishing the recursive call
        async with session_factory() as new_session:
            user = await create_user(user_id, display_name, session=new_session)
            await new_session.commit()
            return user
    # Check if user already exists
    try:
        await get_user(user_id, session=session)
        raise ResourceExistsError("User already exists in database.")
    except ResourceNotFoundError:
        pass

    user = User(userId=user_id, displayName=display_name)
    session.add(user)
    # call flush here so the final commit is back in the function where the session was created
    await session.flush()
    await session.refresh(user)
    return user


async def get_user(user_id: str, session: AsyncSession | None = None) -> User:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_user(user_id, session=new_session)

    user: User | None = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFoundError("User not found in database.")
    return user


async def update_user_display_name(
    user_id: str, display_name: str, session: AsyncSession | None = None
) -> User:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            updated_user = await update_user_display_name(
                user_id, display_name, session=new_session
            )
            await new_session.commit()
            return updated_user

    result = await session.execute(select(User).where(User.userId == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found in database.")
    user.displayName = display_name
    await session.flush()
    await session.refresh(user)
    return user


async def create_music_provider(
    provider_id: str, name: str, session: AsyncSession | None = None
) -> MusicProvider:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            provider = await create_music_provider(
                provider_id, name, session=new_session
            )
            await new_session.commit()
            return provider
    try:
        await get_music_provider(provider_id, session=session)
        raise ResourceExistsError("Provider already exists in database.")
    except ResourceNotFoundError:
        pass

    provider = MusicProvider(providerId=provider_id, name=name)
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return provider


async def get_music_provider(
    provider_id: str, session: AsyncSession | None = None
) -> MusicProvider:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_music_provider(provider_id, session=new_session)

    provider: MusicProvider | None = await session.get(MusicProvider, provider_id)
    if provider is None:
        raise ResourceNotFoundError("Provider not found in database.")
    return provider


# helper methods to make sure room_id and join_code are unique
async def _get_unique_room_id(session: AsyncSession) -> str:
    while True:
        new_id = generate_room_id()
        if await session.get(Room, new_id) is None:
            return new_id


async def _get_unique_join_code(session: AsyncSession) -> str:
    while True:
        new_code = generate_join_code()
        result = await session.execute(select(Room).where(Room.joinCode == new_code))
        if result.scalar_one_or_none() is None:
            return new_code


async def create_room(
    user_id: str,
    supported_provider_id: str,
    name: str | None = None,
    session: AsyncSession | None = None,
) -> Room:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            room = await create_room(
                user_id, supported_provider_id, name, session=new_session
            )
            await new_session.commit()
            return room

    join_code = await _get_unique_join_code(session)

    if name is None:
        name = f"Room_{join_code}"

    # no try except to see if room already exists, since a new unique id is generated (room will always have a different id)

    room = Room(
        roomId=await _get_unique_room_id(session),
        joinCode=join_code,
        name=name,
        hostedBy=user_id,
        supportedProviderId=supported_provider_id,
        status=RoomStatus.ACTIVE,
    )
    session.add(room)
    await session.flush()
    await session.refresh(room)
    return room


async def get_room(room_id: str, session: AsyncSession | None = None) -> Room:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_room(room_id, session=new_session)

    room: Room | None = await session.get(Room, room_id)
    if room is None:
        raise ResourceNotFoundError("Room not found in database.")
    return room


async def get_room_by_join_code(
    join_code: str, session: AsyncSession | None = None
) -> Room:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_room_by_join_code(join_code, session=new_session)

    result = await session.execute(select(Room).where(Room.joinCode == join_code))
    room: Room | None = result.scalar_one_or_none()
    if room is None:
        raise ResourceNotFoundError("Room not found in database.")
    return room


async def get_all_active_rooms_by_join_codes(
    join_codes: Sequence[str], session: AsyncSession | None = None
) -> list[str]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_all_active_rooms_by_join_codes(
                join_codes, session=new_session
            )

    normalized = [code.strip().upper() for code in join_codes if code.strip()]
    if not normalized:
        return []

    result = await session.execute(
        select(Room.joinCode).where(
            Room.joinCode.in_(normalized),
            Room.status == RoomStatus.ACTIVE,
        )
    )
    # Keep order stable by preserving first appearance in input.
    available = set(result.scalars().all())
    return [code for code in normalized if code in available]


async def update_room_status(
    room_id: str, status: RoomStatus, session: AsyncSession | None = None
) -> Room:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            room = await update_room_status(room_id, status, session=new_session)
            await new_session.commit()
            return room

    room = await get_room(room_id, session=session)

    room.status = status
    await session.flush()
    await session.refresh(room)
    return room


# refactor to use update_room_membership
async def leave_room(
    user_id: str, room_id: str, session: AsyncSession | None = None
) -> RoomMembership:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            updated_membership = await leave_room(user_id, room_id, session=new_session)
            await new_session.commit()
            return updated_membership

    result = await session.execute(
        select(RoomMembership).where(
            RoomMembership.userId == user_id, RoomMembership.roomId == room_id
        )
    )

    membership: RoomMembership | None = result.scalar_one_or_none()

    if not membership:
        raise ResourceNotFoundError(
            "Membership between this user and the room was not found in the database."
        )

    membership.leftAt = datetime.now(UTC)
    membership.membershipStatus = MembershipStatus.INACTIVE
    await session.flush()
    await session.refresh(membership)
    return membership


async def create_room_membership(
    user_id: str, room_id: str, session: AsyncSession | None = None
) -> RoomMembership:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            membership = await create_room_membership(
                user_id, room_id, session=new_session
            )
            await new_session.commit()
            return membership

    try:
        await get_room_membership(user_id, room_id, session=session)
        raise ResourceExistsError("User is already a member of this room.")
    except ResourceNotFoundError:
        pass

    membership = RoomMembership(userId=user_id, roomId=room_id)
    session.add(membership)
    await session.flush()
    await session.refresh(membership)
    return membership


async def get_room_membership(
    user_id: str, room_id: str, session: AsyncSession | None = None
) -> RoomMembership:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_room_membership(user_id, room_id, session=new_session)

    result = await session.execute(
        select(RoomMembership).where(
            RoomMembership.userId == user_id, RoomMembership.roomId == room_id
        )
    )
    membership: RoomMembership | None = result.scalar_one_or_none()
    if membership is None:
        raise ResourceNotFoundError("Room-Membership not found in database.")
    return membership


async def get_room_memberships(room_id: str) -> Sequence[RoomMembership]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(RoomMembership).where(RoomMembership.roomId == room_id)
        )
        return result.scalars().all()


async def get_room_active_memberships(
    room_id: str, session: AsyncSession | None = None
) -> Sequence[Row[tuple[RoomMembership, User]]]:
    """Get all active members of a room with their user data"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_room_active_memberships(room_id, session=new_session)

    result = await session.execute(
        select(RoomMembership, User)
        .join(User)
        .where(
            RoomMembership.roomId == room_id,
            RoomMembership.membershipStatus == MembershipStatus.ACTIVE,
        )
    )
    return result.all()


async def update_room_membership_status(
    user_id: str,
    room_id: str,
    status: MembershipStatus,
    session: AsyncSession | None = None,
) -> RoomMembership:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            updated_membership = await update_room_membership_status(
                user_id, room_id, status, session=new_session
            )
            await new_session.commit()
            return updated_membership

    result = await session.execute(
        select(RoomMembership).where(
            RoomMembership.userId == user_id,
            RoomMembership.roomId == room_id,
        )
    )

    membership: RoomMembership | None = result.scalar_one_or_none()
    if membership is None:
        raise ResourceNotFoundError("Room Membership not found in database.")

    membership.membershipStatus = status
    if status == MembershipStatus.ACTIVE:
        membership.leftAt = None
        membership.joinedAt = datetime.now(UTC)

    if (
        status == MembershipStatus.INACTIVE
        or status == MembershipStatus.KICKED
        or status == MembershipStatus.BANNED
    ):
        membership.leftAt = datetime.now(UTC)

    return membership


async def create_provider_account(
    user_id: str, provider_id: str, external_user_id: str
) -> ProviderAccount:
    """Create a new provider account for a user"""
    # Check if user exists
    user = await get_user(user_id)
    if not user:
        raise ValueError("User not found")

    # Check if provider account already exists for this user and provider
    session_factory = get_session_factory()
    async with session_factory() as session:
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
    session_factory = get_session_factory()
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


async def get_queue_entries(room_id: str) -> Sequence[QueueEntry]:
    """Get all queue entries for a room, ordered by position"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
        )
        return result.scalars().all()


async def get_current_playback_session(room_id: str) -> PlaybackSession | None:
    """Get the current playback session for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PlaybackSession)
            .where(PlaybackSession.roomId == room_id)
            .order_by(PlaybackSession.startedAt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_track(track_id: str) -> Track | None:
    """Get track by ID or return None if not found"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await session.get(Track, track_id)


async def create_track(track_data: dict[str, object]) -> Track:
    """Create a new track"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        track = Track(**track_data)
        session.add(track)
        await session.commit()
        await session.refresh(track)
        return track


async def create_queue_entry(queue_entry_data: dict[str, object]) -> QueueEntry:
    """Create a new queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        queue_entry = QueueEntry(**queue_entry_data)
        session.add(queue_entry)
        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def get_queue_entry(queue_entry_id: str) -> QueueEntry | None:
    """Get queue entry by ID"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await session.get(QueueEntry, queue_entry_id)


async def update_queue_entry(
    queue_entry_id: str, updates: dict[str, object]
) -> QueueEntry:
    """Update a queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        queue_entry = await session.get(QueueEntry, queue_entry_id)
        if not queue_entry:
            raise ValueError("Queue entry not found")

        for key, value in updates.items():
            setattr(queue_entry, key, value)

        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def get_queue_entry_by_track(room_id: str, track_id: str) -> QueueEntry | None:
    """Get queue entry by room ID and track ID"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry).where(
                QueueEntry.roomId == room_id, QueueEntry.trackId == track_id
            )
        )
        return result.scalar_one_or_none()


async def create_playback_session(playback_data: dict[str, object]) -> PlaybackSession:
    """Create a new playback session"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        playback_session = PlaybackSession(**playback_data)
        session.add(playback_session)
        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def update_playback_session(
    playback_session_id: str, updates: dict[str, object]
) -> PlaybackSession:
    """Update a playback session"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        playback_session = await session.get(PlaybackSession, playback_session_id)
        if not playback_session:
            raise ValueError("Playback session not found")

        for key, value in updates.items():
            setattr(playback_session, key, value)

        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def get_song_feedback_by_queue_entry(
    queue_entry_id: str,
) -> Sequence[SongFeedback]:
    """Get all song feedback for a queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
            )
        )
        return result.scalars().all()


async def get_song_feedback(queue_entry_id: str, user_id: str) -> SongFeedback | None:
    """Get song feedback for a user"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
                SongFeedback.userId == user_id,
            )
        )
        return result.scalar_one_or_none()


async def create_or_update_song_feedback(
    feedback_data: dict[str, object],
) -> SongFeedback:
    """Create or update song feedback"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = await get_song_feedback(
            str(feedback_data["queueEntryId"]), str(feedback_data["userId"])
        )

        if existing:
            existing = await session.merge(existing)
            for key, value in feedback_data.items():
                setattr(existing, key, value)
            feedback = existing
        else:
            feedback = SongFeedback(**feedback_data)
            session.add(feedback)

        await session.flush()
        await session.refresh(feedback)
        await session.commit()
        return feedback


async def delete_song_feedback(queue_entry_id: str, user_id: str) -> None:
    """Delete song feedback"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        feedback = await get_song_feedback(queue_entry_id, user_id)
        if feedback:
            await session.delete(feedback)
            await session.commit()


async def get_max_queue_position(room_id: str) -> int:
    """Get the maximum queue position for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(func.max(QueueEntry.position)).where(QueueEntry.roomId == room_id)
        )
        max_position = result.scalar_one_or_none()
        return int(max_position or 0)


async def get_playing_queue_entry(room_id: str) -> QueueEntry | None:
    """Get the currently playing queue entry for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
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
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_provider_account_by_user(
    user_id: str, provider_id: str
) -> ProviderAccount | None:
    """Get a provider account for a user and provider, or None."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        return result.scalar_one_or_none()


async def create_or_update_provider_account_tokens(
    user_id: str,
    provider_id: str,
    external_user_id: str,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime,
) -> ProviderAccount:
    """Create or update a provider account with OAuth tokens."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.externalUserId = external_user_id
            existing.accessToken = access_token
            existing.refreshToken = refresh_token
            existing.tokenExpiresAt = token_expires_at
            existing.status = AccountStatus.ACTIVE
            await session.commit()
            await session.refresh(existing)
            return existing

        provider_account = ProviderAccount(
            providerAccountId=str(uuid.uuid4()),
            externalUserId=external_user_id,
            userId=user_id,
            providerId=provider_id,
            status=AccountStatus.ACTIVE,
            accessToken=access_token,
            refreshToken=refresh_token,
            tokenExpiresAt=token_expires_at,
        )
        session.add(provider_account)
        await session.commit()
        await session.refresh(provider_account)
        return provider_account


async def update_provider_account_tokens(
    provider_account_id: str,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: str | None = None,
) -> ProviderAccount:
    """Update OAuth tokens on an existing provider account."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        pa = await session.get(ProviderAccount, provider_account_id)
        if not pa:
            raise ValueError("Provider account not found")
        pa.accessToken = access_token
        pa.tokenExpiresAt = token_expires_at
        if refresh_token is not None:
            pa.refreshToken = refresh_token
        await session.commit()
        await session.refresh(pa)
        return pa


async def get_next_queued_entry(room_id: str) -> QueueEntry | None:
    """Get the next queued entry by highest vote score, then earliest position."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(
                QueueEntry.roomId == room_id,
                QueueEntry.status == QueueEntryStatus.QUEUED,
            )
            .order_by(QueueEntry.voteScore.desc(), QueueEntry.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def check_db_health() -> dict[str, object]:
    """Check if database is healthy by executing a simple query"""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "ok"}
        return {"status": "error", "detail": "Query returned unexpected result"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
