from __future__ import annotations

from fastapi import HTTPException

from services.providers.base import MusicProviderClient
from services.providers.spotify_client import SpotifyProviderClient

_provider_clients: dict[str, MusicProviderClient] = {
    "spotify": SpotifyProviderClient(),
}


def get_provider_client(provider_id: str) -> MusicProviderClient:
    normalized = provider_id.strip().lower()
    client = _provider_clients.get(normalized)
    if client is None:
        raise HTTPException(status_code=400, detail=f"Unsupported music provider: {provider_id}")
    return client
