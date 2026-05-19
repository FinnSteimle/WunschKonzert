from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from models.domain import ProviderAccount


@dataclass(frozen=True)
class ProviderTrack:
    track_id: str
    provider_track_id: str
    title: str
    artist: str
    album: str
    duration: int
    cover_url: str
    deep_link: str

    def to_api_dict(self) -> dict[str, str | int]:
        return {
            "trackId": self.track_id,
            "providerTrackId": self.provider_track_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "coverUrl": self.cover_url,
            "deepLink": self.deep_link,
        }


class MusicProviderClient(Protocol):
    provider_id: str

    async def search_tracks(
        self, query: str, user_id: str | None = None
    ) -> list[ProviderTrack]: ...

    async def find_track_for_user(
        self, *, user_id: str, title: str, artist: str
    ) -> ProviderTrack | None: ...

    def is_linked(self, account: ProviderAccount) -> bool:
        """Return True if the account holds the credentials required by this provider."""
        ...
