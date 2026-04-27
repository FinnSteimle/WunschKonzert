from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import PlaybackSession


async def get_current_playback_session(
    room_id: str, session: AsyncSession | None = None
) -> PlaybackSession | None:
    """Get the current playback session for a room"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_current_playback_session(room_id, session=new_session)

    result = await session.execute(
        select(PlaybackSession)
        .where(PlaybackSession.roomId == room_id)
        .order_by(PlaybackSession.startedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_playback_session(
    playback_data: dict[str, object], session: AsyncSession | None = None
) -> PlaybackSession:
    """Create a new playback session"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            playback_session = await create_playback_session(
                playback_data, session=new_session
            )
            await new_session.commit()
            return playback_session

    playback_session = PlaybackSession(**playback_data)
    session.add(playback_session)
    await session.flush()
    await session.refresh(playback_session)
    return playback_session


async def update_playback_session(
    playback_session_id: str,
    updates: dict[str, object],
    session: AsyncSession | None = None,
) -> PlaybackSession:
    """Update a playback session"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            updated_session = await update_playback_session(
                playback_session_id, updates, session=new_session
            )
            await new_session.commit()
            return updated_session

    playback_session = await session.get(PlaybackSession, playback_session_id)
    if not playback_session:
        raise ResourceNotFoundError("Playback session not found")

    for key, value in updates.items():
        setattr(playback_session, key, value)

    await session.flush()
    await session.refresh(playback_session)
    return playback_session
