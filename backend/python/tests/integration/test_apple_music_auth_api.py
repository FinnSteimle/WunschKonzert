import uuid

import pytest

from models.domain import AccountStatus
from repositories import music_provider_repo, user_repo

pytestmark = pytest.mark.integration

_FAKE_DEV_TOKEN = "fake-developer-token"


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    """Single-response httpx.AsyncClient stub for Apple Music API calls."""

    response: _FakeResponse | None = None

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, **kwargs):  # type: ignore[override]
        assert _FakeAsyncClient.response is not None, "No response configured"
        resp = _FakeAsyncClient.response
        _FakeAsyncClient.response = None
        return resp


def _stub_dev_token():
    return _FAKE_DEV_TOKEN


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    _FakeAsyncClient.response = None
    monkeypatch.setattr("services.providers.apple_music_jwt._sign", _stub_dev_token)
    yield


async def _seed_provider(db_session) -> None:
    await music_provider_repo.create_music_provider(
        "apple-music", "Apple Music", db_session
    )
    await db_session.commit()


# ── developer-token ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_developer_token_returns_token(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await db_session.commit()

    response = await client.get(
        "/auth/apple-music/developer-token", params={"user_id": user_id}
    )

    assert response.status_code == 200
    assert response.json() == {"developer_token": _FAKE_DEV_TOKEN}


@pytest.mark.asyncio
async def test_developer_token_missing_credentials_returns_503(client, monkeypatch):
    monkeypatch.setattr("services.providers.apple_music_jwt._sign", None)
    monkeypatch.delenv("APPLE_MUSIC_TEAM_ID", raising=False)
    monkeypatch.delenv("APPLE_MUSIC_KEY_ID", raising=False)
    monkeypatch.delenv("APPLE_MUSIC_PRIVATE_KEY", raising=False)
    # Reset cache so the signer re-reads env
    monkeypatch.setattr("services.providers.apple_music_jwt._cached_token", None)

    response = await client.get(
        "/auth/apple-music/developer-token",
        params={"user_id": str(uuid.uuid4())},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "apple_music_not_configured"


# ── link ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_link_success_stores_mut_and_storefront(client, db_session, monkeypatch):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)

    _FakeAsyncClient.response = _FakeResponse({"data": [{"id": "us"}]}, status_code=200)
    monkeypatch.setattr(
        "api.routers.apple_music_auth.httpx.AsyncClient", _FakeAsyncClient
    )

    response = await client.post(
        "/auth/apple-music/link",
        json={
            "user_id": user_id,
            "music_user_token": "valid-mut",
            "display_name": "Test User",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"storefront": "us", "display_name": "Test User"}

    pa = await music_provider_repo.get_provider_account_by_user(user_id, "apple-music")
    assert pa is not None
    assert pa.accessToken == "valid-mut"
    assert pa.refreshToken is None
    assert pa.storefront == "us"
    assert pa.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_link_subscription_error_returns_403(client, db_session, monkeypatch):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)

    _FakeAsyncClient.response = _FakeResponse({}, status_code=403)
    monkeypatch.setattr(
        "api.routers.apple_music_auth.httpx.AsyncClient", _FakeAsyncClient
    )

    response = await client.post(
        "/auth/apple-music/link",
        json={"user_id": user_id, "music_user_token": "mut", "display_name": "Test"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "subscription_error"


@pytest.mark.asyncio
async def test_link_invalid_token_returns_401(client, db_session, monkeypatch):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)

    _FakeAsyncClient.response = _FakeResponse({}, status_code=401)
    monkeypatch.setattr(
        "api.routers.apple_music_auth.httpx.AsyncClient", _FakeAsyncClient
    )

    response = await client.post(
        "/auth/apple-music/link",
        json={"user_id": user_id, "music_user_token": "bad-mut", "display_name": "T"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_music_user_token"


@pytest.mark.asyncio
async def test_link_apple_error_returns_400(client, db_session, monkeypatch):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)

    _FakeAsyncClient.response = _FakeResponse({}, status_code=400)
    monkeypatch.setattr(
        "api.routers.apple_music_auth.httpx.AsyncClient", _FakeAsyncClient
    )

    response = await client.post(
        "/auth/apple-music/link",
        json={"user_id": user_id, "music_user_token": "mut", "display_name": "T"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_link_relink_clears_suspended_status(client, db_session, monkeypatch):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)
    # Seed a suspended account (simulates revoked MUT)
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="old-mut",
    )
    from sqlalchemy import select

    from core.database import get_session_factory
    from models.domain import ProviderAccount

    session_factory = get_session_factory()
    async with session_factory() as s:
        result = await s.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == "apple-music",
            )
        )
        pa = result.scalar_one()
        pa.status = AccountStatus.SUSPENDED
        await s.commit()

    _FakeAsyncClient.response = _FakeResponse({"data": [{"id": "us"}]}, status_code=200)
    monkeypatch.setattr(
        "api.routers.apple_music_auth.httpx.AsyncClient", _FakeAsyncClient
    )

    response = await client.post(
        "/auth/apple-music/link",
        json={
            "user_id": user_id,
            "music_user_token": "new-mut",
            "display_name": "Test",
        },
    )

    assert response.status_code == 200
    pa_after = await music_provider_repo.get_provider_account_by_user(
        user_id, "apple-music"
    )
    assert pa_after is not None
    assert pa_after.status == AccountStatus.ACTIVE
    assert pa_after.accessToken == "new-mut"


# ── token ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_token_returns_mut_for_linked_user(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="stored-mut",
        storefront="us",
    )

    response = await client.get("/auth/apple-music/token", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json() == {"music_user_token": "stored-mut"}


@pytest.mark.asyncio
async def test_token_unlinked_returns_404(client):
    response = await client.get(
        "/auth/apple-music/token", params={"user_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_linked"


@pytest.mark.asyncio
async def test_token_suspended_returns_409(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Test", db_session)
    await _seed_provider(db_session)
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="revoked-mut",
    )
    from sqlalchemy import select

    from core.database import get_session_factory
    from models.domain import ProviderAccount

    session_factory = get_session_factory()
    async with session_factory() as s:
        result = await s.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == "apple-music",
            )
        )
        pa = result.scalar_one()
        pa.status = AccountStatus.SUSPENDED
        await s.commit()

    response = await client.get("/auth/apple-music/token", params={"user_id": user_id})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "needs_relink"


# ── profile ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_linked_user(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Alice", db_session)
    await _seed_provider(db_session)
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="mut",
        storefront="de",
    )

    response = await client.get(
        "/auth/apple-music/profile", params={"user_id": user_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is True
    assert data["storefront"] == "de"
    assert data["display_name"] == "Alice"
    assert data["needs_relink"] is False


@pytest.mark.asyncio
async def test_profile_unlinked_user(client):
    response = await client.get(
        "/auth/apple-music/profile", params={"user_id": str(uuid.uuid4())}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is False
    assert data["needs_relink"] is False


@pytest.mark.asyncio
async def test_profile_suspended_shows_needs_relink(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Bob", db_session)
    await _seed_provider(db_session)
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="old-mut",
        storefront="us",
    )
    from sqlalchemy import select

    from core.database import get_session_factory
    from models.domain import ProviderAccount

    session_factory = get_session_factory()
    async with session_factory() as s:
        result = await s.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == "apple-music",
            )
        )
        pa = result.scalar_one()
        pa.status = AccountStatus.SUSPENDED
        await s.commit()

    response = await client.get(
        "/auth/apple-music/profile", params={"user_id": user_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is True
    assert data["needs_relink"] is True


# ── gating ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_room_create_gating_apple_music_linked(client, db_session):
    """Apple Music host can create a room with accessToken and no refreshToken."""
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host", db_session)
    await music_provider_repo.create_music_provider(
        "apple-music", "Apple Music", db_session
    )
    await db_session.commit()
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="valid-mut",
    )

    response = await client.post(
        "/create_room",
        json={
            "user_id": user_id,
            "display_name": "Host",
            "name": "AM Room",
            "supported_provider_id": "apple-music",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_room_create_gating_apple_music_unlinked_returns_403(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host", db_session)
    await music_provider_repo.create_music_provider(
        "apple-music", "Apple Music", db_session
    )
    await db_session.commit()

    response = await client.post(
        "/create_room",
        json={
            "user_id": user_id,
            "display_name": "Host",
            "name": "AM Room",
            "supported_provider_id": "apple-music",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_room_create_gating_apple_music_suspended_returns_403(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host", db_session)
    await music_provider_repo.create_music_provider(
        "apple-music", "Apple Music", db_session
    )
    await db_session.commit()
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="apple-music",
        external_user_id=user_id,
        access_token="revoked-mut",
    )
    from sqlalchemy import select

    from core.database import get_session_factory
    from models.domain import ProviderAccount

    session_factory = get_session_factory()
    async with session_factory() as s:
        result = await s.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == "apple-music",
            )
        )
        pa = result.scalar_one()
        pa.status = AccountStatus.SUSPENDED
        await s.commit()

    response = await client.post(
        "/create_room",
        json={
            "user_id": user_id,
            "display_name": "Host",
            "name": "AM Room",
            "supported_provider_id": "apple-music",
        },
    )

    assert response.status_code == 403
