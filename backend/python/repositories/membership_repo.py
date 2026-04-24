from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import ResourceExistsError, ResourceNotFoundError
from models.domain import MembershipStatus, RoomMembership, User


# To be replaced with update_room_membership_status
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
