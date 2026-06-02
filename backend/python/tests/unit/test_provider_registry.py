import pytest
from fastapi import HTTPException

from services.providers.registry import get_provider_client

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("provider_id", "expected_provider_id"),
    [
        ("spotify", "spotify"),
        ("apple-music", "apple-music"),
    ],
)
def test_get_provider_client_registered_provider_exists(
    provider_id, expected_provider_id
):
    client = get_provider_client(provider_id)
    assert client.provider_id == expected_provider_id


def test_get_provider_client_unknown_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        get_provider_client("unknown-provider")
    assert exc_info.value.status_code == 400
    assert "Unsupported music provider" in exc_info.value.detail
