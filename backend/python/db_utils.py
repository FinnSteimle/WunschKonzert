import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database import Room, RoomMembership, User

# Create async engine and session factory
# Ensure we use asyncpg driver for async operations
database_url = os.environ["DATABASE_URL"]
if not database_url.startswith("postgresql+asyncpg"):
    if database_url.startswith("postgresql:"):
        database_url = database_url.replace("postgresql:", "postgresql+asyncpg:", 1)
    else:
        database_url = "postgresql+asyncpg:" + database_url

engine = create_async_engine(database_url)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_user(user_id: str) -> User | None:
    """Get user by ID or return None if not found"""
    async with AsyncSessionLocal() as session:
        return await session.get(User, user_id)


async def get_room(room_id: str) -> Room | None:
    """Get room by ID or return None if not found"""
    async with AsyncSessionLocal() as session:
        return await session.get(Room, room_id)


async def get_room_membership(user_id: str, room_id: str) -> RoomMembership | None:
    """Get existing room membership or return None if not found"""
    async with AsyncSessionLocal() as session:
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

    async with AsyncSessionLocal() as session:
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

    async with AsyncSessionLocal() as session:
        user = User(userId=user_id, displayName=display_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
