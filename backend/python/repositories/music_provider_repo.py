import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.user_repo as user_repo
from core.database import get_session_factory
from core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
)
from models.domain import (
    AccountStatus,
    MusicProvider,
    ProviderAccount,
)


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


async def create_provider_account(
    user_id: str,
    provider_id: str,
    external_user_id: str,
    session: AsyncSession | None = None,
) -> ProviderAccount:
    """Create a new provider account for a user"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            account = await create_provider_account(
                user_id, provider_id, external_user_id, session=new_session
            )
            await new_session.commit()
            return account

    # Check if user exists
    user = await user_repo.get_user(user_id, session=session)
    if not user:
        raise ValueError("User not found")

    # Check if provider account already exists for this user and provider
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
    provider_account = ProviderAccount(
        providerAccountId=str(uuid.uuid4()),
        externalUserId=external_user_id,
        userId=user_id,
        providerId=provider_id,
        status=AccountStatus.ACTIVE,
    )
    session.add(provider_account)
    await session.flush()
    await session.refresh(provider_account)
    return provider_account


async def get_provider_account_by_user(
    user_id: str, provider_id: str, session: AsyncSession | None = None
) -> ProviderAccount | None:
    """Get a provider account for a user and provider, or None."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_provider_account_by_user(
                user_id, provider_id, session=new_session
            )

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
    refresh_token: str | None = None,
    token_expires_at: datetime | None = None,
    storefront: str | None = None,
    session: AsyncSession | None = None,
) -> ProviderAccount:
    """Create or update a provider account with tokens. refresh_token and
    token_expires_at are optional for providers like Apple Music that don't issue them."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            account = await create_or_update_provider_account_tokens(
                user_id,
                provider_id,
                external_user_id,
                access_token,
                refresh_token,
                token_expires_at,
                storefront,
                session=new_session,
            )
            await new_session.commit()
            return account

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
        if storefront is not None:
            existing.storefront = storefront
        await session.flush()
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
        storefront=storefront,
    )
    session.add(provider_account)
    await session.flush()
    await session.refresh(provider_account)
    return provider_account


async def update_provider_account_tokens(
    provider_account_id: str,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: str | None = None,
    session: AsyncSession | None = None,
) -> ProviderAccount:
    """Update OAuth tokens on an existing provider account."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            account = await update_provider_account_tokens(
                provider_account_id,
                access_token,
                token_expires_at,
                refresh_token,
                session=new_session,
            )
            await new_session.commit()
            return account

    pa = await session.get(ProviderAccount, provider_account_id)
    if not pa:
        raise ValueError("Provider account not found")
    pa.accessToken = access_token
    pa.tokenExpiresAt = token_expires_at
    if refresh_token is not None:
        pa.refreshToken = refresh_token
    await session.flush()
    await session.refresh(pa)
    return pa
