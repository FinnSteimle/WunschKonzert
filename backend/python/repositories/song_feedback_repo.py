from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models.domain import SongFeedback


async def get_song_feedback_by_queue_entry(
    queue_entry_id: str, session: AsyncSession | None = None
) -> Sequence[SongFeedback]:
    """Get all song feedback for a queue entry"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_song_feedback_by_queue_entry(
                queue_entry_id, session=new_session
            )

    result = await session.execute(
        select(SongFeedback).where(
            SongFeedback.queueEntryId == queue_entry_id,
        )
    )
    return result.scalars().all()


async def get_song_feedback(
    queue_entry_id: str, user_id: str, session: AsyncSession | None = None
) -> SongFeedback | None:
    """Get song feedback for a user"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_song_feedback(queue_entry_id, user_id, session=new_session)

    result = await session.execute(
        select(SongFeedback).where(
            SongFeedback.queueEntryId == queue_entry_id,
            SongFeedback.userId == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_or_update_song_feedback(
    feedback_data: dict[str, object], session: AsyncSession | None = None
) -> SongFeedback:
    """Create or update song feedback"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            feedback = await create_or_update_song_feedback(
                feedback_data, session=new_session
            )
            await new_session.commit()
            return feedback

    existing = await get_song_feedback(
        str(feedback_data["queueEntryId"]),
        str(feedback_data["userId"]),
        session=session,
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
    return feedback


async def delete_song_feedback(
    queue_entry_id: str, user_id: str, session: AsyncSession | None = None
) -> None:
    """Delete song feedback"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            await delete_song_feedback(queue_entry_id, user_id, session=new_session)
            await new_session.commit()
            return

    feedback = await get_song_feedback(queue_entry_id, user_id, session=session)
    if feedback:
        await session.delete(feedback)
        await session.flush()
