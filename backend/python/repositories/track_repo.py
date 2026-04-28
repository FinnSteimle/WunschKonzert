from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models.domain import Track


async def get_track(track_id: str, session: AsyncSession | None = None) -> Track | None:
    """Get track by ID or return None if not found"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_track(track_id, session=new_session)

    return await session.get(Track, track_id)


async def create_track(
    track_data: dict[str, object], session: AsyncSession | None = None
) -> Track:
    """Create a new track"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            track = await create_track(track_data, session=new_session)
            await new_session.commit()
            return track

    track = Track(**track_data)
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track
