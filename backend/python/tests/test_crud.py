import pytest

import uuid
from models import domain
from repositories import crud


@pytest.mark.asyncio
async def test_create_and_get_user_base_case(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name)
    user: domain.User | None = await crud.get_user(user_id)

    assert user is not None
    assert user.userId == user_id
    assert user.displayName == display_name
