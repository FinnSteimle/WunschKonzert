from datetime import datetime

from models.domain import PlaybackState
from services.playback_service import _determine_playback_updates


def test_determine_playback_updates_pause():
    updates = _determine_playback_updates("pause", 120)
    assert updates["state"] == PlaybackState.PAUSED
    assert isinstance(updates["pausedAt"], datetime)
    assert updates["elapsedTime"] == 120


def test_determine_playback_updates_resume():
    updates = _determine_playback_updates("resume", 150)
    assert updates["state"] == PlaybackState.PLAYING
    assert updates["pausedAt"] is None
    assert updates["elapsedTime"] == 150


def test_determine_playback_updates_stop():
    updates = _determine_playback_updates("stop", None)
    assert updates["state"] == PlaybackState.STOPPED
    assert isinstance(updates["pausedAt"], datetime)
    assert "elapsedTime" not in updates
