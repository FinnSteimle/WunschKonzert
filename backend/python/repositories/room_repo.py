from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from core.identifiers import generate_join_code, generate_room_id
from models.domain import Room, RoomStatus


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
    join_codes: list[str], session: AsyncSession | None = None
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


async def update_host(
    room_id: str, new_user_id: str, session: AsyncSession | None = None
) -> Room:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            room = await update_host(room_id, new_user_id, session=new_session)
            await new_session.commit()
            return room

    room = await get_room(room_id, session=session)

    room.hostedBy = new_user_id
    await session.flush()
    await session.refresh(room)
    return room
