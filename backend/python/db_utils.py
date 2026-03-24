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
    MembershipStatus,
    ProviderAccount,
    Room,
    RoomMembership,
    RoomStatus,
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
