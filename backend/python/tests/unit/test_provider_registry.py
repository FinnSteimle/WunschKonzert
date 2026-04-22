import pytest
from fastapi import HTTPException

from services.providers.registry import get_provider_client

pytestmark = pytest.mark.unit


def test_get_provider_client_spotify_exists():
    client = get_provider_client("spotify")
    assert client.provider_id == "spotify"


def test_get_provider_client_unknown_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        get_provider_client("apple")
    assert exc_info.value.status_code == 400
    assert "Unsupported music provider" in exc_info.value.detail
