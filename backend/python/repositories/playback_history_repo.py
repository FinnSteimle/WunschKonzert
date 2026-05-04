from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.database import get_session_factory
from models.domain import PlaybackHistoryEntry, QueueEntry


async def add_history_entry(
    history_data: dict[str, object], session: AsyncSession | None = None
) -> PlaybackHistoryEntry:
    """Add an entry to the playback history"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            history_entry = await add_history_entry(history_data, session=new_session)
            await new_session.commit()
            return history_entry

    history_entry = PlaybackHistoryEntry(**history_data)
    session.add(history_entry)
    await session.flush()
    await session.refresh(history_entry)
    return history_entry


async def get_history(
    room_id: str, limit: int = 20, session: AsyncSession | None = None
) -> Sequence[PlaybackHistoryEntry]:
    """Get the last N history entries for a room, with track information"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_history(room_id, limit=limit, session=new_session)

    result = await session.execute(
        select(PlaybackHistoryEntry)
        .options(
            joinedload(PlaybackHistoryEntry.queue_entry).joinedload(QueueEntry.track)
        )
        .where(PlaybackHistoryEntry.roomId == room_id)
        .order_by(PlaybackHistoryEntry.playedAt.desc())
        .limit(limit)
    )
    return result.scalars().all()
