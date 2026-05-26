import pytest
from fastapi import HTTPException

from services.room_service import register_or_update_user
from services.room_state_service import JOIN_CODE_RE


def test_join_code_regex_valid():
    assert JOIN_CODE_RE.match("ABCDE2")
    assert JOIN_CODE_RE.match("987654")
    assert JOIN_CODE_RE.match("ZXYWVK")


def test_join_code_regex_invalid():
    # Too short
    assert not JOIN_CODE_RE.match("ABC12")
    # Too long
    assert not JOIN_CODE_RE.match("ABC1234")
    # Forbidden characters (0, 1, I, O)
    assert not JOIN_CODE_RE.match("ABCIO1")
    # Special characters
    assert not JOIN_CODE_RE.match("ABC-12")


# We can't easily test register_or_update_user without mocking the whole repo
# because it's async and calls user_repo. But we can test its validation logic
# if we extract it, or just use Mock.


@pytest.mark.asyncio
async def test_register_or_update_user_empty_raises():
    with pytest.raises(HTTPException) as exc:
        await register_or_update_user("u1", "   ")
    assert exc.value.status_code == 400
    assert "required" in exc.value.detail


@pytest.mark.asyncio
async def test_register_or_update_user_too_long_raises():
    with pytest.raises(HTTPException) as exc:
        await register_or_update_user("u1", "a" * 61)
    assert exc.value.status_code == 400
    assert "too long" in exc.value.detail
