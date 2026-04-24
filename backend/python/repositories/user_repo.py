from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import ResourceExistsError, ResourceNotFoundError
from models.domain import User


async def create_user(
    user_id: str, display_name: str, session: AsyncSession | None = None
) -> User:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            user = await create_user(user_id, display_name, session=new_session)
            await new_session.commit()
            return user

    try:
        await get_user(user_id, session=session)
        raise ResourceExistsError("User already exists in database.")
    except ResourceNotFoundError:
        pass

    user = User(userId=user_id, displayName=display_name)
    session.add(user)
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
